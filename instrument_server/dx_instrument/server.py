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
    ACK, ENQ, EOT, MLLP_END, MLLP_START, NAK, STX, extract_mllp,
    verify_astm_frame, wrap_mllp,
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

    # ── HL7 / MLLP ───────────────────────────────────────────────────────────

    def _handle_hl7(self) -> None:
        messages, self.buffer = extract_mllp(self.buffer)
        for message in messages:
            accepted = self._dispatch(message, "hl7")
            self.request.sendall(wrap_mllp(self._hl7_ack(message, accepted)))

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
                 interface_id: str | None = None, idle_timeout: float = 300.0):
        self.protocol = protocol
        self.client = client
        self.interface_id = interface_id
        self.idle_timeout = idle_timeout
        super().__init__(address, InstrumentHandler)
