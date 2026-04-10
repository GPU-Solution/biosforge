"""SPI flash region extraction and manipulation.

Handles extracting individual regions from a full SPI dump and
preparing them for recombination.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional

from .flash_descriptor import FlashDescriptor, FlashRegion, RegionType


@dataclass
class ExtractedRegion:
    """A region extracted from a flash image with metadata."""
    type: RegionType
    data: bytes
    source: str  # Description of where this data came from
    md5: str
    sha256: str

    @property
    def name(self) -> str:
        return self.type.display_name

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def size_str(self) -> str:
        kb = self.size / 1024
        if kb >= 1024:
            return f"{kb / 1024:.2f} MB"
        return f"{kb:.0f} KB"

    @property
    def fill_pct(self) -> float:
        """Percentage of bytes that are NOT 0xFF (data fill)."""
        if self.size == 0:
            return 0.0
        ff_count = self.data.count(b"\xff")
        return (1.0 - ff_count / self.size) * 100


def extract_region(data: bytes, region: FlashRegion, source: str) -> ExtractedRegion:
    """Extract a region from a full SPI flash image.

    Args:
        data: Full SPI flash image bytes.
        region: FlashRegion describing the region bounds.
        source: Human-readable description of the source file.

    Returns:
        ExtractedRegion with the raw data and checksums.
    """
    raw = region.extract(data)
    return ExtractedRegion(
        type=region.type,
        data=raw,
        source=source,
        md5=hashlib.md5(raw).hexdigest(),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def extract_all_regions(data: bytes, descriptor: FlashDescriptor,
                        source: str) -> dict[RegionType, ExtractedRegion]:
    """Extract all enabled regions from a flash image.

    Args:
        data: Full SPI flash image bytes.
        descriptor: Parsed flash descriptor.
        source: Human-readable source description.

    Returns:
        Dict mapping RegionType to ExtractedRegion.
    """
    regions = {}
    for rtype, region in descriptor.regions.items():
        if region.enabled:
            regions[rtype] = extract_region(data, region, source)
    return regions


def compare_regions(a: ExtractedRegion, b: ExtractedRegion) -> dict:
    """Compare two extracted regions."""
    identical = a.data == b.data
    size_match = a.size == b.size

    diff_count = 0
    if size_match and not identical:
        diff_count = sum(1 for x, y in zip(a.data, b.data) if x != y)

    return {
        "identical": identical,
        "size_match": size_match,
        "a_size": a.size,
        "b_size": b.size,
        "a_source": a.source,
        "b_source": b.source,
        "a_md5": a.md5,
        "b_md5": b.md5,
        "diff_bytes": diff_count,
        "diff_pct": (diff_count / a.size * 100) if size_match and a.size > 0 else None,
    }
