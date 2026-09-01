"""Conservative magic-number checks for recovered content."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Signature:
    name: str
    marker: bytes
    offset: int = 0


KNOWN = (
    Signature("PNG", b"\x89PNG\r\n\x1a\n"),
    Signature("JPEG", b"\xff\xd8\xff"),
    Signature("PDF", b"%PDF"),
    Signature("ZIP/DOCX", b"PK\x03\x04"),
    Signature("ELF", b"\x7fELF"),
)


def identify(data: bytes) -> tuple[str, bool]:
    for item in KNOWN:
        if data[item.offset:].startswith(item.marker):
            return item.name, True
    return "Unknown", False
