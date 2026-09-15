"""Command-line entry point for the instrument server."""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from dx_instrument.client import LisClient
from dx_instrument.server import InstrumentServer

logger = logging.getLogger("dx.instrument")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dx-instrument-server",
        description="Accept analyser connections and forward results to Dx.",
    )
    parser.add_argument("--host", default=os.environ.get("INSTRUMENT_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("INSTRUMENT_PORT", "5150")))
    parser.add_argument("--protocol", choices=("astm", "hl7"),
                        default=os.environ.get("INSTRUMENT_PROTOCOL", "astm"))
    parser.add_argument("--lis-url", default=os.environ.get("LIS_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("INSTRUMENT_INGEST_TOKEN", ""))
    parser.add_argument("--interface-id", default=os.environ.get("INSTRUMENT_INTERFACE_ID"),
                        help="Dx InstrumentInterface id this listener represents.")
    parser.add_argument("--spool", default=os.environ.get("INSTRUMENT_SPOOL", "instrument-spool.jsonl"))
    parser.add_argument("--replay-interval", type=int, default=60,
                        help="Seconds between spool replay attempts (0 disables).")
    parser.add_argument("--idle-timeout", type=float, default=300.0)
    parser.add_argument(
        "--host-query", action="store_true",
        default=os.environ.get("INSTRUMENT_HOST_QUERY", "").lower() in {"1", "true", "yes"},
        help=(
            "Answer analyser work-list queries (ASTM Q records, HL7 QBP^Q11). "
            "The interface must also be configured as bidirectional in Dx."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
    )

    if not args.token:
        logger.error("No ingest token supplied. Set INSTRUMENT_INGEST_TOKEN or pass --token.")
        return 2

    client = LisClient(args.lis_url, args.token, spool=Path(args.spool))
    server = InstrumentServer(
        (args.host, args.port), protocol=args.protocol, client=client,
        interface_id=args.interface_id, idle_timeout=args.idle_timeout,
        host_query_enabled=args.host_query,
    )

    stopping = threading.Event()

    def shutdown(signum, frame):
        logger.info("Shutting down…")
        stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.replay_interval:
        def replay_loop():
            while not stopping.wait(args.replay_interval):
                sent = client.replay_spool()
                if sent:
                    logger.info("Replayed %s spooled payload(s)", sent)

        threading.Thread(target=replay_loop, name="spool-replay", daemon=True).start()

    logger.info(
        "Listening on %s:%s (%s) → %s%s",
        args.host, args.port, args.protocol.upper(), client.ingest_url,
        " [host query enabled]" if args.host_query else "",
    )
    server.serve_forever()
    server.server_close()
    logger.info("Stopped cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
