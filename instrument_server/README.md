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
| `--host-query` | Answer the analyser's work-list queries as well as receiving results |

## Host query (bidirectional)

An analyser can ask the LIS what to run on a specimen it has just loaded,
instead of running a fixed panel or being keyed by hand.

```bash
python -m dx_instrument.cli --port 5150 --protocol astm \
  --interface-id <InstrumentInterface id> --host-query
```

The listener recognises an ASTM `Q` record or an HL7 `QBP^Q11`, asks Dx over
`POST /api/middleware/query/`, and answers the analyser in its own dialect —
ASTM `O` records, or an HL7 `RSP^K11`.

Host query is **opt-in on both sides**: this flag, *and* the
`InstrumentInterface` record in Dx set to bidirectional. Either one off and the
query is refused. An analyser handed a work list it was not configured to
expect will run tests nobody ordered.

Dx answers with outstanding tests only, on an open order only, translated into
the analyser's own codes via the interface's code map. A query is never
answered with a test that already has a result: an analyser re-running a
verified result would silently overwrite a report somebody has already acted
on.

Unlike a result, a query is **not spooled** if the LIS is unreachable. An
analyser holding a tube on the deck is waiting for the answer, and a late reply
is worse than a clean "I do not know" — the analyser parks the sample and asks
again.

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
  checks, critical value detection, reflex rules and notifiable conditions —
  and the decision rules, including autoverification where the laboratory has
  enabled it for that analyte.
