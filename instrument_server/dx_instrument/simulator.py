"""Analyser simulator, for exercising the interface without hardware."""
from __future__ import annotations

import argparse
import logging
import random
import socket
import time

from dx_instrument.protocol import ACK, ENQ, EOT, build_astm_frame, wrap_mllp

logger = logging.getLogger("dx.instrument.simulator")

PANEL = [
    ("GLU", (3.0, 9.0), "mmol/L"),
    ("NA", (130.0, 148.0), "mmol/L"),
    ("K", (3.0, 5.6), "mmol/L"),
    ("CREA", (55.0, 180.0), "umol/L"),
]


def astm_records(accession: str, instrument: str) -> list[str]:
    stamp = time.strftime("%Y%m%d%H%M%S")
    records = [
        f"H|\\^&|||{instrument}^1.0|||||||P|1394-97|{stamp}",
        "P|1|||||||U",
        f"O|1|{accession}|{accession}||R|{stamp}|||||||||||||||||O",
    ]
    for index, (code, (low, high), units) in enumerate(PANEL, start=1):
        value = round(random.uniform(low, high), 1)
        records.append(
            f"R|{index}|^^^{code}|{value}|{units}||N||F||{instrument}|{stamp}|{stamp}"
        )
    records.append("L|1|N")
    return records


def hl7_message(accession: str, instrument: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S")
    segments = [
        f"MSH|^~\\&|{instrument}|LAB|DX|LAB|{stamp}||ORU^R01|{accession}|P|2.5",
        "PID|1||UNKNOWN||DOE^JOHN||19700101|U",
        f"OBR|1|{accession}|{accession}|^Panel|||{stamp}",
    ]
    for index, (code, (low, high), units) in enumerate(PANEL, start=1):
        value = round(random.uniform(low, high), 1)
        segments.append(f"OBX|{index}|NM|{code}^^^{code}|1|{value}|{units}|||||F|||{stamp}")
    return "\r".join(segments) + "\r"


def send_astm(sock: socket.socket, accession: str, instrument: str) -> None:
    sock.sendall(ENQ)
    if sock.recv(1) != ACK:
        raise RuntimeError("Analyser handshake refused by the server")

    for sequence, record in enumerate(astm_records(accession, instrument), start=1):
        sock.sendall(build_astm_frame(sequence, record + "\r"))
        response = sock.recv(1)
        if response != ACK:
            raise RuntimeError(f"Frame {sequence} not acknowledged: {response!r}")
    sock.sendall(EOT)


def send_hl7(sock: socket.socket, accession: str, instrument: str) -> None:
    sock.sendall(wrap_mllp(hl7_message(accession, instrument)))
    acknowledgement = sock.recv(4096)
    logger.info("Acknowledgement: %s", acknowledgement.decode("utf-8", errors="replace").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dx-instrument-simulator",
        description="Send simulated analyser results to the instrument server.",
    )
    parser.add_argument("accession", help="Accession number to report against")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5150)
    parser.add_argument("--protocol", choices=("astm", "hl7"), default="astm")
    parser.add_argument("--instrument", default="SIM-1")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    for iteration in range(args.repeat):
        with socket.create_connection((args.host, args.port), timeout=10) as sock:
            if args.protocol == "astm":
                send_astm(sock, args.accession, args.instrument)
            else:
                send_hl7(sock, args.accession, args.instrument)
        logger.info("Sent %s message %s/%s for %s",
                    args.protocol.upper(), iteration + 1, args.repeat, args.accession)
        if iteration + 1 < args.repeat:
            time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
