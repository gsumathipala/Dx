"""Code 128 barcode rendering, as inline SVG.

Why implement it
----------------
A laboratory runs on labels. Accessioning allocates a number and somebody has
to stick it on a tube; the whole chain of custody, the instrument's host query
and every scan at the bench depend on that label existing and being readable.

Code 128 is the right symbology for this: it encodes the full ASCII set,
subset C packs digit pairs into one symbol so an accession number stays short,
and every laboratory scanner in existence reads it. The encoder is about a
hundred lines against a published table, so it is written here rather than
pulled in — a dependency for this would be a supply-chain surface on something
that touches every specimen.

Rendered as SVG so it prints crisply at any size, needs no image pipeline, and
embeds directly in a page the browser already has open.

What this is not
----------------
It is not a print server. A browser printing an SVG will produce a label a
scanner reads, but a production laboratory uses a thermal printer speaking
ZPL — see ``apps.laboratory.labels``.
"""
from __future__ import annotations

#: Code 128 symbol patterns, values 0–106. Each is the bar/space widths of an
#: 11-module symbol (the stop symbol has 13). Straight from the specification.
PATTERNS = [
    "11011001100", "11001101100", "11001100110", "10010011000", "10010001100",
    "10001001100", "10011001000", "10011000100", "10001100100", "11001001000",
    "11001000100", "11000100100", "10110011100", "10011011100", "10011001110",
    "10111001100", "10011101100", "10011100110", "11001110010", "11001011100",
    "11001001110", "11011100100", "11001110100", "11101101110", "11101001100",
    "11100101100", "11100100110", "11101100100", "11100110100", "11100110010",
    "11011011000", "11011000110", "11000110110", "10100011000", "10001011000",
    "10001000110", "10110001000", "10001101000", "10001100010", "11010001000",
    "11000101000", "11000100010", "10110111000", "10110001110", "10001101110",
    "10111011000", "10111000110", "10001110110", "11101110110", "11010001110",
    "11000101110", "11011101000", "11011100010", "11011101110", "11101011000",
    "11101000110", "11100010110", "11101101000", "11101100010", "11100011010",
    "11101111010", "11001000010", "11110001010", "10100110000", "10100001100",
    "10010110000", "10010000110", "10000101100", "10000100110", "10110010000",
    "10110000100", "10011010000", "10011000010", "10000110100", "10000110010",
    "11000010010", "11001010000", "11110111010", "11000010100", "10001111010",
    "10100111100", "10010111100", "10010011110", "10111100100", "10011110100",
    "10011110010", "11110100100", "11110010100", "11110010010", "11011011110",
    "11011110110", "11110110110", "10101111000", "10100011110", "10001011110",
    "10111101000", "10111100010", "11110101000", "11110100010", "10111011110",
    "10111101110", "11101011110", "11110101110", "11110100110", "11110010110",
    "11011011010", "11011010110", "11010110110", "11000100100",
]

START_B = 104
START_C = 105
CODE_B = 100
CODE_C = 99
STOP = 106


def _encode(text: str) -> list[int]:
    """Symbol values for ``text``, switching to subset C for digit runs.

    Subset C encodes two digits per symbol. An accession number like
    ``2026-09-16-0007`` is mostly digits, so this roughly halves the physical
    width — which matters on a 25mm tube label more than it sounds.
    """
    if any(ord(character) > 127 for character in text):
        raise ValueError("Code 128 here encodes ASCII only.")

    values: list[int] = []
    position = 0
    # Start in subset C when at least four leading digits make it worthwhile.
    current = "C" if _digit_run(text, 0) >= 4 else "B"
    values.append(START_C if current == "C" else START_B)

    while position < len(text):
        run = _digit_run(text, position)

        if current == "C":
            if run >= 2:
                values.append(int(text[position:position + 2]))
                position += 2
                continue
            values.append(CODE_B)
            current = "B"
            continue

        # Subset B. Switch to C for a long enough digit run to pay for the
        # switch symbol: four mid-string, or two at the very end.
        if run >= 4 or (run >= 2 and position + run == len(text) and run % 2 == 0):
            values.append(CODE_C)
            current = "C"
            continue

        values.append(ord(text[position]) - 32)
        position += 1

    checksum = values[0]
    for index, value in enumerate(values[1:], start=1):
        checksum += value * index
    values.append(checksum % 103)
    values.append(STOP)
    return values


def _digit_run(text: str, start: int) -> int:
    run = 0
    while start + run < len(text) and text[start + run].isdigit():
        run += 1
    return run


def modules(text: str) -> str:
    """The barcode as a string of '1' (bar) and '0' (space) modules."""
    pattern = "".join(PATTERNS[value] for value in _encode(text))
    return pattern + "11"  # the stop symbol's two trailing bars


def svg(text: str, *, height: int = 40, module_width: float = 1.4,
        quiet_zone: int = 10, show_text: bool = True) -> str:
    """Render ``text`` as a Code 128 barcode in SVG.

    The quiet zone is not decoration. A barcode without clear space either side
    is one a scanner reads intermittently, which in a laboratory means a tube
    that gets keyed by hand at three in the morning.
    """
    bits = modules(text)
    width = (len(bits) + quiet_zone * 2) * module_width
    text_height = 12 if show_text else 0
    total_height = height + text_height + 4

    bars: list[str] = []
    index = 0
    while index < len(bits):
        if bits[index] == "1":
            run = 1
            while index + run < len(bits) and bits[index + run] == "1":
                run += 1
            x = (quiet_zone + index) * module_width
            bars.append(
                f'<rect x="{x:.2f}" y="0" width="{run * module_width:.2f}" '
                f'height="{height}" fill="#000"/>'
            )
            index += run
        else:
            index += 1

    label = ""
    if show_text:
        from xml.sax.saxutils import escape

        label = (
            f'<text x="{width / 2:.2f}" y="{height + text_height}" '
            f'font-family="monospace" font-size="{text_height}" '
            f'text-anchor="middle" fill="#000">{escape(text)}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" '
        f'height="{total_height}" viewBox="0 0 {width:.2f} {total_height}" '
        f'role="img" aria-label="Barcode: {text}">'
        f'<rect width="100%" height="100%" fill="#fff"/>{"".join(bars)}{label}</svg>'
    )


def decode_modules(bits: str) -> str:  # pragma: no cover - used by the tests
    """Reverse ``modules`` back to text. Exists so the encoder is verifiable.

    An encoder nobody can check is an encoder that silently prints labels no
    scanner reads, and you find out at the bench.
    """
    bits = bits[:-2] if bits.endswith("11") else bits
    symbols = [bits[i:i + 11] for i in range(0, len(bits), 11)]
    values = [PATTERNS.index(symbol) for symbol in symbols if len(symbol) == 11]

    if not values or values[-1] != STOP:
        raise ValueError("No stop symbol.")
    values = values[:-1]

    checksum = values.pop()
    expected = values[0] + sum(v * i for i, v in enumerate(values[1:], start=1))
    if checksum != expected % 103:
        raise ValueError("Checksum mismatch.")

    mode = "C" if values[0] == START_C else "B"
    out: list[str] = []
    for value in values[1:]:
        # A symbol's meaning depends on the subset in force. 99 is "switch to
        # subset C" while in B, and the digit pair "99" while already in C;
        # 100 is "switch to subset B" only while in C. Reading them
        # unconditionally decodes "99" as a subset switch and loses the digits.
        if mode != "C" and value == CODE_C:
            mode = "C"
            continue
        if mode == "C" and value == CODE_B:
            mode = "B"
            continue
        out.append(f"{value:02d}" if mode == "C" else chr(value + 32))
    return "".join(out)
