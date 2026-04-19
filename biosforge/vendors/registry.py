"""Vendor parser auto-detection registry.

Tries each registered vendor parser until one matches.
New vendors are added by importing their parser here.
"""

from typing import Optional
from .base import VendorParser, VendorBiosInfo
from .hp import HPParser
from .dell import DellParser


# Register all vendor parsers here.
# Order matters: more specific parsers should come first.
VENDOR_PARSERS: list[VendorParser] = [
    DellParser(),
    HPParser(),
    # LenovoParser(),  # TODO
    # AsusParser(),    # TODO
    # AcerParser(),    # TODO
]


def detect_vendor(data: bytes, filename: str = "") -> Optional[VendorBiosInfo]:
    """Auto-detect vendor and parse a BIOS update image.

    Tries each registered parser in order until one succeeds.

    Args:
        data: Raw file bytes.
        filename: Original filename (helps with detection).

    Returns:
        VendorBiosInfo if a parser matched, None otherwise.
    """
    for parser in VENDOR_PARSERS:
        if parser.can_parse(data, filename):
            try:
                return parser.parse(data, filename)
            except ValueError:
                continue
    return None


def get_supported_vendors() -> list[str]:
    """Get list of supported vendor names."""
    return [p.vendor_name for p in VENDOR_PARSERS]
