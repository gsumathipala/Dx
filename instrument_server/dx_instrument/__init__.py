"""Dx instrument interface server.

Listens for analyser connections, decodes ASTM E1381/E1394 and HL7 v2 MLLP
traffic, and posts the parsed results to the Dx ingest endpoint.

Ported from the TypeScript ``instrument-server``.
"""

__version__ = "2.0.0"
