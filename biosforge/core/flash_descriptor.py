"""Intel Flash Descriptor parser.

Parses the Intel Flash Descriptor (IFD) found at the beginning of SPI flash
dumps. The descriptor defines the layout of all regions in the flash chip.

Reference: Intel Flash Descriptor spec + coreboot ifdtool + UEFITool.
"""

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


IFD_SIGNATURE = 0x0FF0A55A
IFD_SIGNATURE_OFFSET = 0x10


class RegionType(IntEnum):
    DESCRIPTOR = 0
    BIOS = 1
    ME = 2
    GBE = 3
    PDR = 4
    DEVICE_EXP1 = 5
    BIOS2 = 6
    UCODE = 7
    EC = 8
    DEVICE_EXP2 = 9
    IE = 10
    PLATFORM = 11

    @property
    def display_name(self) -> str:
        names = {
            0: "Descriptor", 1: "BIOS", 2: "Intel ME", 3: "GbE",
            4: "PDR", 5: "Dev Exp 1", 6: "BIOS 2", 7: "Microcode",
            8: "EC", 9: "Dev Exp 2", 10: "IE", 11: "Platform",
        }
        return names.get(self.value, f"Region {self.value}")


@dataclass
class FlashRegion:
    """A single region within the SPI flash."""
    type: RegionType
    base: int
    limit: int
    enabled: bool

    @property
    def size(self) -> int:
        if not self.enabled:
            return 0
        return self.limit - self.base + 1

    @property
    def name(self) -> str:
        return self.type.display_name

    def extract(self, data: bytes) -> bytes:
        if not self.enabled:
            return b""
        return data[self.base:self.limit + 1]

    def __repr__(self) -> str:
        if not self.enabled:
            return f"FlashRegion({self.name}: disabled)"
        size_kb = self.size / 1024
        if size_kb >= 1024:
            size_str = f"{size_kb / 1024:.2f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"
        return (
            f"FlashRegion({self.name}: "
            f"0x{self.base:08X}-0x{self.limit:08X}, {size_str})"
        )


@dataclass
class MasterAccess:
    """Access permissions for a flash master."""
    name: str
    read_regions: list[int] = field(default_factory=list)
    write_regions: list[int] = field(default_factory=list)


@dataclass
class FlashDescriptor:
    """Parsed Intel Flash Descriptor."""
    raw: bytes
    signature_valid: bool
    chip_size: int
    num_regions: int
    regions: dict[RegionType, FlashRegion] = field(default_factory=dict)
    masters: list[MasterAccess] = field(default_factory=list)

    # Raw register values
    flmap0: int = 0
    flmap1: int = 0
    flmap2: int = 0
    fcba: int = 0  # Flash Component Base Address
    frba: int = 0  # Flash Region Base Address
    fmba: int = 0  # Flash Master Base Address

    @property
    def descriptor_region(self) -> Optional[FlashRegion]:
        return self.regions.get(RegionType.DESCRIPTOR)

    @property
    def bios_region(self) -> Optional[FlashRegion]:
        return self.regions.get(RegionType.BIOS)

    @property
    def me_region(self) -> Optional[FlashRegion]:
        return self.regions.get(RegionType.ME)

    @property
    def gbe_region(self) -> Optional[FlashRegion]:
        return self.regions.get(RegionType.GBE)

    def get_enabled_regions(self) -> list[FlashRegion]:
        return [r for r in self.regions.values() if r.enabled]

    def summary(self) -> str:
        lines = [
            f"Intel Flash Descriptor (valid={self.signature_valid})",
            f"  Chip size: {self.chip_size / 1024 / 1024:.0f} MB",
            f"  Regions ({self.num_regions} defined):",
        ]
        for r in self.regions.values():
            status = f"0x{r.base:08X}-0x{r.limit:08X} ({r.size / 1024:.0f} KB)" if r.enabled else "disabled"
            lines.append(f"    {r.name:12s}: {status}")
        return "\n".join(lines)


def parse_descriptor(data: bytes) -> FlashDescriptor:
    """Parse an Intel Flash Descriptor from a full SPI flash dump.

    Args:
        data: Full SPI flash image (must start at offset 0).

    Returns:
        FlashDescriptor with all parsed regions.

    Raises:
        ValueError: If the data is too small or descriptor signature is missing.
    """
    if len(data) < 0x1000:
        raise ValueError(f"Data too small for flash descriptor: {len(data)} bytes")

    sig = struct.unpack_from("<I", data, IFD_SIGNATURE_OFFSET)[0]
    sig_valid = sig == IFD_SIGNATURE

    if not sig_valid:
        raise ValueError(
            f"Invalid Flash Descriptor signature at 0x{IFD_SIGNATURE_OFFSET:X}: "
            f"0x{sig:08X} (expected 0x{IFD_SIGNATURE:08X})"
        )

    # Parse FLMAP registers
    flmap0 = struct.unpack_from("<I", data, 0x14)[0]
    flmap1 = struct.unpack_from("<I", data, 0x18)[0]
    flmap2 = struct.unpack_from("<I", data, 0x1C)[0]

    # Extract base addresses from FLMAP0
    # Bits 7:0   = FCBA (Flash Component Base Address >> 4)
    # Bits 9:8   = NC   (Number of Components)
    # Bits 23:16 = FRBA (Flash Region Base Address >> 4)
    # Bits 26:24 = NR   (Number of Regions)
    fcba = (flmap0 & 0xFF) << 4
    frba = ((flmap0 >> 16) & 0xFF) << 4
    nr = (flmap0 >> 24) & 0x7

    # Extract from FLMAP1
    fmba = (flmap1 & 0xFF) << 4

    # Parse regions from FRBA
    regions = {}
    chip_size = len(data)
    for i in range(12):
        reg_val = struct.unpack_from("<I", data, frba + i * 4)[0]
        base_val = reg_val & 0x7FFF
        limit_val = (reg_val >> 16) & 0x7FFF

        rtype = RegionType(i)

        # Region is disabled if:
        # - base > limit (standard disabled marker like 0x00007FFF)
        # - raw value is 0xFFFFFFFF (all-ones = unused flash)
        # - both base and limit are 0x7FFF (max values = disabled)
        # - computed addresses exceed chip size
        disabled = (
            base_val > limit_val
            or reg_val == 0xFFFFFFFF
            or (base_val == 0x7FFF and limit_val == 0x7FFF)
        )

        if disabled:
            regions[rtype] = FlashRegion(
                type=rtype, base=0, limit=0, enabled=False
            )
        else:
            base = base_val << 12
            limit = (limit_val << 12) | 0xFFF
            # Also disable if region extends beyond chip
            if limit >= chip_size:
                regions[rtype] = FlashRegion(
                    type=rtype, base=0, limit=0, enabled=False
                )
            else:
                regions[rtype] = FlashRegion(
                    type=rtype, base=base, limit=limit, enabled=True
                )

    # Descriptor region is always at 0x000-0xFFF even if register says otherwise
    regions[RegionType.DESCRIPTOR] = FlashRegion(
        type=RegionType.DESCRIPTOR, base=0, limit=0xFFF, enabled=True
    )

    # Parse master access from FMBA
    masters = []
    master_names = ["BIOS", "ME", "GbE"]
    for i, name in enumerate(master_names):
        if fmba + (i + 1) * 4 <= len(data):
            mval = struct.unpack_from("<I", data, fmba + i * 4)[0]
            read_r = []
            write_r = []
            for bit in range(12):
                if mval & (1 << (bit + 16)):
                    read_r.append(bit)
                if mval & (1 << bit):
                    write_r.append(bit)
            masters.append(MasterAccess(name=name, read_regions=read_r, write_regions=write_r))

    return FlashDescriptor(
        raw=bytes(data[0:0x1000]),
        signature_valid=sig_valid,
        chip_size=len(data),
        num_regions=nr,
        regions=regions,
        masters=masters,
        flmap0=flmap0,
        flmap1=flmap1,
        flmap2=flmap2,
        fcba=fcba,
        frba=frba,
        fmba=fmba,
    )


def has_descriptor(data: bytes) -> bool:
    """Check if data starts with a valid Intel Flash Descriptor."""
    if len(data) < IFD_SIGNATURE_OFFSET + 4:
        return False
    sig = struct.unpack_from("<I", data, IFD_SIGNATURE_OFFSET)[0]
    return sig == IFD_SIGNATURE
