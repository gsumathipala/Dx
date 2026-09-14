"""Low-level framing for the two supported instrument protocols.

ASTM E1381 uses a checksummed frame delimited by STX/ETX with an odd/even frame
number, inside an ENQ/ACK handshake. HL7 v2 is transported with MLLP, a much
simpler start/end block wrapper.
"""
from __future__ import annotations

# ── ASTM control characters (ASTM E1381) ─────────────────────────────────────
ENQ = b"\x05"
ACK = b"\x06"
NAK = b"\x15"
STX = b"\x02"
ETX = b"\x03"
ETB = b"\x17"
EOT = b"\x04"
CR = b"\x0d"
LF = b"\x0a"

# ── MLLP block characters (HL7 v2 transport) ─────────────────────────────────
MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"


def astm_checksum(frame: bytes) -> str:
    """Checksum of an ASTM frame body: modulo-256 sum as two hex digits.

    The body is everything after STX up to and including ETX/ETB.
    """
    return f"{sum(frame) % 256:02X}"


def build_astm_frame(sequence: int, text: str, *, final: bool = True) -> bytes:
    """Wrap ``text`` in an ASTM frame with its checksum."""
    body = f"{sequence % 8}{text}".encode("ascii", errors="replace")
    terminator = ETX if final else ETB
    checksum = astm_checksum(body + terminator)
    return STX + body + terminator + checksum.encode("ascii") + CR + LF


def verify_astm_frame(frame: bytes) -> tuple[bool, str]:
    """Validate a received frame's checksum and return its payload.

    A frame that fails its checksum is rejected rather than parsed — a
    corrupted result is worse than a missing one.
    """
    if not frame.startswith(STX):
        return False, ""

    body = frame[1:]
    for terminator in (ETX, ETB):
        index = body.find(terminator)
        if index == -1:
            continue
        content = body[:index]
        checked = body[: index + 1]
        received = body[index + 1: index + 3].decode("ascii", errors="replace").upper()
        if received != astm_checksum(checked):
            return False, ""
        # Drop the leading frame-sequence digit.
        return True, content[1:].decode("latin-1")

    return False, ""


def wrap_mllp(message: str) -> bytes:
    return MLLP_START + message.encode("utf-8") + MLLP_END


def extract_mllp(buffer: bytes) -> tuple[list[str], bytes]:
    """Pull complete MLLP blocks out of a buffer, returning the remainder."""
    messages: list[str] = []
    while True:
        start = buffer.find(MLLP_START)
        if start == -1:
            return messages, b""
        end = buffer.find(MLLP_END, start)
        if end == -1:
            return messages, buffer[start:]
        messages.append(buffer[start + 1: end].decode("utf-8", errors="replace"))
        buffer = buffer[end + len(MLLP_END):]
