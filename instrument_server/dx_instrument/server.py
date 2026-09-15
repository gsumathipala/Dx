"""TCP listener accepting analyser connections.

Each connection is handled on its own thread. ASTM connections are driven by
the ENQ/ACK handshake; HL7 connections exchange MLLP blocks and are answered
with an ACK acknowledgement.
"""
from __future__ import annotations

import logging
import socket
import socketserver
import threading
import time

from dx_instrument.client import LisClient
from dx_instrument.parser import parse
from dx_instrument.protocol import (
    ACK, ENQ, EOT, MLLP_END, MLLP_START, NAK, STX, build_astm_frame,
    extract_mllp, verify_astm_frame, wrap_mllp,
)

logger = logging.getLogger("dx.instrument.server")


class InstrumentHandler(socketserver.BaseRequestHandler):
    """Handles one analyser connection for the lifetime of the session."""

    def setup(self) -> None:
        self.request.settimeout(self.server.idle_timeout)
        self.buffer = b""
        self.astm_payload: list[str] = []
        logger.info("Connection from %s", self.client_address[0])

    def handle(self) -> None:
        while True:
            try:
                chunk = self.request.recv(4096)
            except socket.timeout:
                logger.info("Idle timeout, closing %s", self.client_address[0])
                return
            except OSError as error:
                logger.warning("Connection error from %s: %s", self.client_address[0], error)
                return

            if not chunk:
                return

            self.buffer += chunk
            if self.server.protocol == "hl7":
                self._handle_hl7()
            else:
                self._handle_astm()

    # ── ASTM ─────────────────────────────────────────────────────────────────

    def _handle_astm(self) -> None:
        while self.buffer:
            if self.buffer.startswith(ENQ):
                self.buffer = self.buffer[1:]
                self.request.sendall(ACK)
                continue

            if self.buffer.startswith(EOT):
                self.buffer = self.buffer[1:]
                self._flush_astm()
                continue

            if self.buffer.startswith(STX):
                end = self.buffer.find(b"\x0d\x0a")
                if end == -1:
                    return  # Frame not yet complete.
                frame, self.buffer = self.buffer[: end + 2], self.buffer[end + 2:]
                valid, text = verify_astm_frame(frame)
                if valid:
                    self.astm_payload.append(text)
                    self.request.sendall(ACK)
                else:
                    # A bad checksum asks the analyser to retransmit rather than
                    # letting a corrupted result through.
                    logger.warning("ASTM checksum failure from %s", self.client_address[0])
                    self.request.sendall(NAK)
                continue

            # Unrecognised leading byte — discard it and resynchronise.
            self.buffer = self.buffer[1:]

    def _flush_astm(self) -> None:
        if not self.astm_payload:
            return
        payload, self.astm_payload = "\r".join(self.astm_payload), []
        self._dispatch(payload, "astm")

    def _answer_astm_query(self, specimen_ids: list[str]) -> None:
        """Send a work list back to the analyser as ASTM O records.

        The analyser has a tube on the deck and is waiting. Each specimen it
        asked about gets one order record naming the tests the LIS wants, or a
        terminator with no orders if there is nothing to do — which the
        analyser reads as "park this sample", not as an error.
        """
        if not self.server.host_query_enabled:
            logger.info("Query received but host query is not enabled on this listener")
            return

        records = ["H|\\^&|||Dx^1|||||||P|1"]
        sequence = 1

        for specimen_id in specimen_ids:
            answer = self.server.client.query(specimen_id, self.server.interface_id)
            tests = (answer or {}).get("tests") or []
            if not tests:
                continue
            for test_code in tests:
                records.append(
                    f"O|{sequence}|{specimen_id}||^^^{test_code}|R||||||||||||||||||O"
                )
                sequence += 1

        records.append(f"L|1|{'N' if sequence > 1 else 'F'}")

        try:
            self.request.sendall(ENQ)
            for index, record in enumerate(records, start=1):
                self.request.sendall(build_astm_frame(index, record + "\r"))
            self.request.sendall(EOT)
            logger.info("Answered query with %s order record(s)", sequence - 1)
        except OSError as error:
            logger.warning("Could not answer the analyser's query: %s", error)

    # ── HL7 / MLLP ───────────────────────────────────────────────────────────

    def _handle_hl7(self) -> None:
        messages, self.buffer = extract_mllp(self.buffer)
        for message in messages:
            parsed = parse(message, "hl7")
            if parsed.is_query:
                self.request.sendall(wrap_mllp(self._hl7_query_response(message, parsed)))
                continue
            accepted = self._dispatch(message, "hl7")
            self.request.sendall(wrap_mllp(self._hl7_ack(message, accepted)))

    def _hl7_query_response(self, message: str, parsed) -> str:
        """An RSP^K11 answering a QBP^Q11 specimen work-list query."""
        control_id = self._control_id(message)
        stamp = time.strftime("%Y%m%d%H%M%S")

        if not self.server.host_query_enabled:
            return (
                f"MSH|^~\\&|DX|LAB|||{stamp}||RSP^K11|{control_id}|P|2.5\r"
                f"MSA|AR|{control_id}|Host query is not enabled on this listener\r"
            )

        segments = [
            f"MSH|^~\\&|DX|LAB|||{stamp}||RSP^K11|{control_id}|P|2.5",
            f"MSA|AA|{control_id}",
            f"QAK|{control_id}|OK",
        ]
        index = 1
        for specimen_id in parsed.queries:
            answer = self.server.client.query(specimen_id, self.server.interface_id)
            for test_code in (answer or {}).get("tests") or []:
                segments.append(f"OBR|{index}||{specimen_id}|{test_code}")
                index += 1
        if index == 1:
            segments[2] = f"QAK|{control_id}|NF"  # no data found
        return "\r".join(segments) + "\r"

    @staticmethod
    def _control_id(message: str) -> str:
        for segment in message.replace("\n", "\r").split("\r"):
            if segment.startswith("MSH"):
                fields = segment.split("|")
                return fields[9] if len(fields) > 9 else ""
        return ""

    @staticmethod
    def _hl7_ack(message: str, accepted: bool) -> str:
        control_id = ""
        for segment in message.replace("\n", "\r").split("\r"):
            if segment.startswith("MSH"):
                fields = segment.split("|")
                if len(fields) > 9:
                    control_id = fields[9]
                break
        stamp = time.strftime("%Y%m%d%H%M%S")
        code = "AA" if accepted else "AE"
        return (
            f"MSH|^~\\&|DX|LAB|||{stamp}||ACK^R01|{control_id}|P|2.5\r"
            f"MSA|{code}|{control_id}\r"
        )

    # ── Delivery ─────────────────────────────────────────────────────────────

    def _dispatch(self, payload: str, protocol: str) -> bool:
        parsed = parse(payload, protocol)

        if parsed.is_query:
            # A query is a question, not a result. Answer it and stop.
            self._answer_astm_query(parsed.queries)
            return True

        if parsed.is_empty:
            logger.info("No results in %s message from %s", protocol, self.client_address[0])
            return True
        if not parsed.accession:
            logger.error("Message from %s carries no accession number — cannot route",
                         self.client_address[0])
            return False

        logger.info("Forwarding %s result(s) for %s", len(parsed.results), parsed.accession)
        return self.server.client.send(parsed.as_payload(self.server.interface_id))


class InstrumentServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, *, protocol: str, client: LisClient,
                 interface_id: str | None = None, idle_timeout: float = 300.0,
                 host_query_enabled: bool = False):
        self.protocol = protocol
        self.client = client
        self.interface_id = interface_id
        self.idle_timeout = idle_timeout
        #: Off unless the listener was started with --host-query. An analyser
        #: that receives a work list it was not configured to expect will run
        #: tests nobody ordered, so this is opt-in per listener as well as per
        #: interface in the LIS.
        self.host_query_enabled = host_query_enabled
        super().__init__(address, InstrumentHandler)
