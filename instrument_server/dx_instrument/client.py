"""Posts parsed instrument results to the Dx ingest endpoint.

Delivery must not be lost when the LIS is briefly unavailable, so failures are
retried with backoff and then written to a spool file the server replays on its
next successful connection.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("dx.instrument.client")


class LisClient:
    def __init__(self, base_url: str, token: str, *, spool: Path | None = None,
                 timeout: float = 10.0, attempts: int = 3):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.attempts = attempts
        self.spool = spool or Path("instrument-spool.jsonl")

    @property
    def ingest_url(self) -> str:
        return f"{self.base_url}/api/middleware/ingest/"

    def send(self, payload: dict) -> bool:
        """Post one payload, spooling it if every attempt fails."""
        body = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(self.attempts):
            try:
                request = urllib.request.Request(
                    self.ingest_url, data=body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.token}",
                    },
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    applied = result.get("applied", 0)
                    errors = result.get("errors") or []
                    if errors:
                        logger.warning("LIS accepted %s result(s) with errors: %s", applied, errors)
                    else:
                        logger.info("LIS accepted %s result(s) for %s", applied, payload.get("accession"))
                    return True

            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")[:200]
                last_error = error
                # 4xx other than 429 will not succeed on retry.
                if 400 <= error.code < 500 and error.code != 429:
                    logger.error("LIS rejected payload (%s): %s", error.code, detail)
                    self._spool(payload)
                    return False
                logger.warning("LIS error %s, retrying: %s", error.code, detail)

            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                logger.warning("LIS unreachable, retrying: %s", error)

            time.sleep(0.5 * (2**attempt))

        logger.error("Spooling payload after %s attempts: %s", self.attempts, last_error)
        self._spool(payload)
        return False

    def _spool(self, payload: dict) -> None:
        try:
            self.spool.parent.mkdir(parents=True, exist_ok=True)
            with self.spool.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        except OSError:
            logger.exception("Could not spool payload — results may be lost: %s", payload)

    def replay_spool(self) -> int:
        """Re-send anything that could not be delivered earlier."""
        if not self.spool.exists() or self.spool.stat().st_size == 0:
            return 0

        working = self.spool.with_suffix(".replaying")
        self.spool.rename(working)

        sent, failed = 0, []
        with working.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.error("Discarding unparsable spooled line")
                    continue
                # Send without re-spooling on failure; keep the line instead.
                if self._send_once(payload):
                    sent += 1
                else:
                    failed.append(line)

        if failed:
            with self.spool.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(failed) + "\n")
        working.unlink(missing_ok=True)
        return sent

    def _send_once(self, payload: dict) -> bool:
        try:
            request = urllib.request.Request(
                self.ingest_url, data=json.dumps(payload).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.token}"},
            )
            with urllib.request.urlopen(request, timeout=self.timeout):
                return True
        except Exception:
            return False
