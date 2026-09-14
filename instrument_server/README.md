# Dx instrument server

Accepts analyser connections over TCP, decodes ASTM E1381/E1394 or HL7 v2
(MLLP), and posts the parsed results to the Dx ingest endpoint.

It is a standalone process with no third-party dependencies — only the Python
standard library — so it can run on a laboratory workstation next to the
analyser rather than on the application server.

## Running

```bash
cd instrument_server
export INSTRUMENT_INGEST_TOKEN=...      # must match the Dx setting
python -m dx_instrument.cli --port 5150 --protocol astm --lis-url http://dx:8000
```

Useful options:

| Option | Purpose |
| --- | --- |
| `--protocol astm\|hl7` | Wire protocol the analyser speaks |
| `--interface-id` | Dx `InstrumentInterface` id, so results are attributed to a configured interface |
| `--spool` | File holding payloads the LIS could not accept yet |
| `--replay-interval` | How often to retry spooled payloads (0 disables) |
| `--idle-timeout` | Close a connection after this many idle seconds |

## Testing without an analyser

```bash
python -m dx_instrument.simulator 2026-01-02-0001 --protocol astm
python -m dx_instrument.simulator 2026-01-02-0001 --protocol hl7
```

## Behaviour worth knowing

* **Checksums are enforced.** An ASTM frame that fails its checksum is answered
  with NAK so the analyser retransmits. A corrupted result is never forwarded.
* **Nothing is dropped.** If the LIS is unreachable the payload is written to
  the spool file and retried; a 4xx rejection is spooled too, so it can be
  inspected rather than lost.
* **Results are attributed to the interface**, never to a person — the Dx audit
  trail records them as `instrument:<name>`.
* **Instrument results run the full clinical engine** on the Dx side: delta
  checks, critical value detection, reflex rules and notifiable conditions.
