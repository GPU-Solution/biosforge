"""Flashable image builder.

Combines regions from different sources (dump, vendor BIOS, clean ME)
into a single flashable SPI image. This is the core operation of biosforge.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .flash_descriptor import FlashDescriptor, RegionType, parse_descriptor
from .regions import ExtractedRegion


@dataclass
class BuildSource:
    """Describes where a region's data comes from in the build."""
    region: RegionType
    source_name: str
    size: int
    md5: str


@dataclass
class BuildResult:
    """Result of building a flashable image."""
    data: bytes
    size: int
    md5: str
    sha256: str
    sources: list[BuildSource] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def save(self, path: str | Path) -> None:
        """Write the built image to a file."""
        Path(path).write_bytes(self.data)

    def summary(self) -> str:
        lines = [
            f"Build Result: {self.size:,} bytes ({self.size / 1024 / 1024:.0f} MB)",
            f"  MD5:    {self.md5}",
            f"  SHA256: {self.sha256}",
            "",
            "  Regions:",
        ]
        for s in self.sources:
            lines.append(
                f"    {s.region.display_name:12s}: "
                f"{s.size / 1024:.0f} KB from {s.source_name}"
            )
        if self.warnings:
            lines.append("")
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append(f"    ! {w}")
        return "\n".join(lines)


class ImageBuilder:
    """Builds a flashable SPI image from components.

    Usage:
        builder = ImageBuilder(dump_data, "my_dump.bin")
        builder.set_bios(hp_bios_data, "HP Q85_013100")
        builder.set_me(clean_me_data, "vinafix clean ME")
        result = builder.build()
        result.save("output.bin")
    """

    def __init__(self, base_dump: bytes, dump_name: str = "dump"):
        """Initialize builder with a base SPI dump.

        The base dump provides the flash descriptor and the default
        data for all regions. Individual regions can then be overridden
        with data from other sources.

        Args:
            base_dump: Full SPI flash dump (must have valid descriptor).
            dump_name: Human-readable name for the dump source.
        """
        self.base_dump = base_dump
        self.dump_name = dump_name
        self.chip_size = len(base_dump)
        self.descriptor = parse_descriptor(base_dump)

        # Region overrides: RegionType -> (data, source_name)
        self._overrides: dict[RegionType, tuple[bytes, str]] = {}
        self._warnings: list[str] = []

    def set_bios(self, data: bytes, source: str = "vendor BIOS") -> None:
        """Override the BIOS region with new data.

        Args:
            data: Raw BIOS region data (must match expected size).
            source: Description of the data source.
        """
        bios = self.descriptor.bios_region
        if bios is None or not bios.enabled:
            raise ValueError("Base dump has no BIOS region")

        if len(data) != bios.size:
            raise ValueError(
                f"BIOS data size mismatch: got {len(data)} bytes, "
                f"expected {bios.size} bytes "
                f"(0x{bios.base:X}-0x{bios.limit:X})"
            )
        self._overrides[RegionType.BIOS] = (data, source)

    def set_me(self, data: bytes, source: str = "clean ME") -> None:
        """Override the ME region with new data.

        Args:
            data: Raw ME region data (must match expected size).
            source: Description of the data source.
        """
        me = self.descriptor.me_region
        if me is None or not me.enabled:
            raise ValueError("Base dump has no ME region")

        if len(data) != me.size:
            raise ValueError(
                f"ME data size mismatch: got {len(data)} bytes, "
                f"expected {me.size} bytes "
                f"(0x{me.base:X}-0x{me.limit:X})"
            )
        self._overrides[RegionType.ME] = (data, source)

    def set_descriptor(self, data: bytes, source: str = "custom descriptor") -> None:
        """Override the descriptor region (use with caution)."""
        if len(data) != 0x1000:
            raise ValueError(
                f"Descriptor must be exactly 4096 bytes, got {len(data)}"
            )
        self._overrides[RegionType.DESCRIPTOR] = (data, source)

    def set_region(self, region_type: RegionType, data: bytes,
                   source: str = "custom") -> None:
        """Override any region with custom data."""
        region = self.descriptor.regions.get(region_type)
        if region is None or not region.enabled:
            raise ValueError(f"Region {region_type.display_name} not present in dump")

        if len(data) != region.size:
            raise ValueError(
                f"{region_type.display_name} size mismatch: "
                f"got {len(data)}, expected {region.size}"
            )
        self._overrides[region_type] = (data, source)

    def build(self) -> BuildResult:
        """Build the final flashable image.

        Starts with the base dump and applies all region overrides.

        Returns:
            BuildResult with the complete image and metadata.
        """
        output = bytearray(self.base_dump)
        sources = []
        self._warnings.clear()

        # Apply each region (overridden or from base dump)
        for rtype, region in self.descriptor.regions.items():
            if not region.enabled:
                continue

            if rtype in self._overrides:
                data, source_name = self._overrides[rtype]
                output[region.base:region.limit + 1] = data
                sources.append(BuildSource(
                    region=rtype,
                    source_name=source_name,
                    size=len(data),
                    md5=hashlib.md5(data).hexdigest(),
                ))
            else:
                chunk = self.base_dump[region.base:region.limit + 1]
                sources.append(BuildSource(
                    region=rtype,
                    source_name=f"{self.dump_name} (original)",
                    size=len(chunk),
                    md5=hashlib.md5(chunk).hexdigest(),
                ))

        # Validate the output
        self._validate_output(bytes(output))

        return BuildResult(
            data=bytes(output),
            size=len(output),
            md5=hashlib.md5(output).hexdigest(),
            sha256=hashlib.sha256(output).hexdigest(),
            sources=sources,
            warnings=list(self._warnings),
        )

    def _validate_output(self, data: bytes) -> None:
        """Run validation checks on the built image."""
        # Check descriptor is still valid
        try:
            out_desc = parse_descriptor(data)
        except ValueError as e:
            self._warnings.append(f"Output descriptor invalid: {e}")
            return

        # Check reset vector (last 16 bytes) is not all FF
        reset_vector = data[-16:]
        if reset_vector == b"\xff" * 16:
            self._warnings.append(
                "Reset vector area (last 16 bytes) is all 0xFF - "
                "BIOS may not boot"
            )

        # Check BIOS region has some non-FF data
        bios = out_desc.bios_region
        if bios and bios.enabled:
            bios_data = data[bios.base:bios.limit + 1]
            ff_pct = bios_data.count(b"\xff") / len(bios_data) * 100
            if ff_pct > 99:
                self._warnings.append(
                    f"BIOS region is {ff_pct:.1f}% empty (0xFF) - "
                    "likely invalid"
                )

        # Check ME $FPT exists if ME region is present
        me = out_desc.me_region
        if me and me.enabled:
            me_data = data[me.base:me.limit + 1]
            if b"$FPT" not in me_data[:0x100]:
                self._warnings.append(
                    "ME region does not contain $FPT signature near start - "
                    "ME firmware may be invalid"
                )
