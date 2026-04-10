"""Intel ME (Management Engine) region parser.

Parses the $FPT (Flash Partition Table) header and partition entries
from the ME region of an SPI flash dump.

Reference: platomav/MEAnalyzer, corna/me_cleaner, UEFITool meparser.
"""

import struct
from dataclasses import dataclass, field
from typing import Optional


FPT_SIGNATURE = b"$FPT"
CPD_SIGNATURE = b"$CPD"


@dataclass
class MEPartition:
    """A single partition in the ME Flash Partition Table."""
    name: str
    offset: int
    length: int

    @property
    def size_kb(self) -> float:
        return self.length / 1024

    @property
    def is_empty(self) -> bool:
        return self.length == 0

    def __repr__(self) -> str:
        if self.is_empty:
            return f"MEPartition({self.name}: empty)"
        return (
            f"MEPartition({self.name}: "
            f"offset=0x{self.offset:08X}, {self.size_kb:.0f} KB)"
        )


@dataclass
class MEInfo:
    """Parsed information from the ME region."""
    fpt_offset: int  # Offset of $FPT within the ME region data
    fpt_version: bytes
    num_partitions: int
    partitions: list[MEPartition] = field(default_factory=list)

    # Region-level info
    region_offset: int = 0   # Absolute offset in the full SPI image
    region_size: int = 0
    data_fill_pct: float = 0.0  # Percentage of non-0xFF bytes

    # Optional version string (from FTPR or $MN2 header)
    version: Optional[str] = None

    @property
    def has_ftpr(self) -> bool:
        return any(p.name == "FTPR" for p in self.partitions)

    @property
    def has_fitc(self) -> bool:
        return any(p.name == "FITC" for p in self.partitions)

    @property
    def partition_names(self) -> list[str]:
        return [p.name for p in self.partitions if not p.is_empty]

    def summary(self) -> str:
        lines = [
            f"Intel ME Region",
            f"  $FPT at offset 0x{self.fpt_offset:X} "
            f"(version bytes: {self.fpt_version.hex()})",
            f"  Partitions: {self.num_partitions}",
            f"  Data fill: {self.data_fill_pct:.1f}%",
        ]
        if self.version:
            lines.insert(1, f"  ME version: {self.version}")
        for p in self.partitions:
            if p.is_empty:
                lines.append(f"    {p.name:6s}: (empty)")
            else:
                lines.append(
                    f"    {p.name:6s}: offset=0x{p.offset:08X}, "
                    f"size={p.size_kb:.0f} KB"
                )
        return "\n".join(lines)


def parse_me_region(data: bytes, region_offset: int = 0) -> MEInfo:
    """Parse the ME region from raw bytes.

    Args:
        data: Raw bytes of the ME region only (not the full SPI image).
        region_offset: Absolute offset of this region in the full SPI image
                      (for reference/display only).

    Returns:
        MEInfo with partition table and metadata.

    Raises:
        ValueError: If $FPT signature is not found.
    """
    # Find $FPT signature - usually at offset 0x10 but can vary
    fpt_off = _find_fpt(data)
    if fpt_off is None:
        raise ValueError("$FPT signature not found in ME region data")

    # Parse $FPT header (32 bytes)
    num_entries = struct.unpack_from("<I", data, fpt_off + 4)[0]
    fpt_version = data[fpt_off + 8:fpt_off + 12]

    # Sanity check
    if num_entries > 64:
        raise ValueError(f"Unreasonable number of $FPT entries: {num_entries}")

    # Parse partition entries (each 32 bytes, starting after 32-byte header)
    partitions = []
    entry_base = fpt_off + 0x20
    for i in range(num_entries):
        entry_off = entry_base + i * 0x20
        if entry_off + 0x20 > len(data):
            break

        name_bytes = data[entry_off:entry_off + 4]
        name = name_bytes.decode("ascii", errors="replace").rstrip("\x00")
        part_offset = struct.unpack_from("<I", data, entry_off + 8)[0]
        part_length = struct.unpack_from("<I", data, entry_off + 12)[0]

        partitions.append(MEPartition(
            name=name, offset=part_offset, length=part_length
        ))

    # Calculate data fill percentage
    ff_count = data.count(b"\xff")
    fill_pct = (1.0 - ff_count / len(data)) * 100 if len(data) > 0 else 0

    # Try to extract ME version from $MN2 manifest header
    version = _find_me_version(data)

    return MEInfo(
        fpt_offset=fpt_off,
        fpt_version=fpt_version,
        num_partitions=num_entries,
        partitions=partitions,
        region_offset=region_offset,
        region_size=len(data),
        data_fill_pct=fill_pct,
        version=version,
    )


def _find_fpt(data: bytes) -> Optional[int]:
    """Find the $FPT signature in ME region data."""
    # Common offsets: 0x10, 0x00
    for test_off in [0x10, 0x00]:
        if test_off + 4 <= len(data) and data[test_off:test_off + 4] == FPT_SIGNATURE:
            return test_off

    # Brute force search (aligned to 0x10)
    for off in range(0, min(len(data), 0x10000), 0x10):
        if data[off:off + 4] == FPT_SIGNATURE:
            return off

    return None


def _find_me_version(data: bytes) -> Optional[str]:
    """Try to extract ME firmware version from $MN2 manifest header.

    The $MN2 header is found inside the FTPR partition and contains
    the ME version at a known offset.
    """
    mn2_sig = b"$MN2"
    pos = 0
    while pos < len(data):
        idx = data.find(mn2_sig, pos)
        if idx == -1:
            break

        # $MN2 header: version is at offset +4 (major.minor.hotfix.build)
        # The exact offset depends on the ME generation
        if idx + 24 <= len(data):
            major = struct.unpack_from("<H", data, idx + 4)[0]
            minor = struct.unpack_from("<H", data, idx + 6)[0]
            hotfix = struct.unpack_from("<H", data, idx + 8)[0]
            build = struct.unpack_from("<H", data, idx + 10)[0]

            # Sanity check: ME versions are typically 6.x-16.x
            if 1 <= major <= 30 and minor < 100:
                return f"{major}.{minor}.{hotfix}.{build}"

        pos = idx + 4

    return None


def has_me_signature(data: bytes) -> bool:
    """Check if data contains a valid ME $FPT signature."""
    return _find_fpt(data) is not None


def compare_me_regions(me_a: MEInfo, me_b: MEInfo) -> dict:
    """Compare two ME regions and return differences.

    Returns a dict with comparison details useful for deciding
    which ME region to use in a rebuild.
    """
    parts_a = set(me_a.partition_names)
    parts_b = set(me_b.partition_names)

    return {
        "partitions_only_in_a": parts_a - parts_b,
        "partitions_only_in_b": parts_b - parts_a,
        "partitions_common": parts_a & parts_b,
        "a_count": me_a.num_partitions,
        "b_count": me_b.num_partitions,
        "a_fill_pct": me_a.data_fill_pct,
        "b_fill_pct": me_b.data_fill_pct,
        "a_version": me_a.version,
        "b_version": me_b.version,
        "version_match": me_a.fpt_version == me_b.fpt_version,
    }
