"""Base class for vendor-specific BIOS image parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VendorBiosInfo:
    """Information extracted from a vendor BIOS update image."""
    vendor: str
    model: Optional[str] = None
    version: Optional[str] = None
    bios_data: Optional[bytes] = None  # Extracted BIOS region
    me_data: Optional[bytes] = None    # Extracted ME data (if present)
    header_size: int = 0
    total_size: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def has_bios(self) -> bool:
        return self.bios_data is not None and len(self.bios_data) > 0

    @property
    def has_me(self) -> bool:
        return self.me_data is not None and len(self.me_data) > 0

    def summary(self) -> str:
        lines = [f"Vendor BIOS Image: {self.vendor}"]
        if self.model:
            lines.append(f"  Model: {self.model}")
        if self.version:
            lines.append(f"  Version: {self.version}")
        lines.append(f"  Total size: {self.total_size:,} bytes")
        lines.append(f"  Header: {self.header_size} bytes")
        if self.has_bios:
            lines.append(
                f"  BIOS data: {len(self.bios_data):,} bytes "
                f"({len(self.bios_data) / 1024 / 1024:.2f} MB)"
            )
        if self.has_me:
            lines.append(
                f"  ME data: {len(self.me_data):,} bytes "
                f"({len(self.me_data) / 1024 / 1024:.2f} MB) [partial]"
            )
        for note in self.notes:
            lines.append(f"  Note: {note}")
        return "\n".join(lines)


class VendorParser(ABC):
    """Abstract base class for vendor BIOS parsers."""

    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Human-readable vendor name."""
        ...

    @abstractmethod
    def can_parse(self, data: bytes, filename: str = "") -> bool:
        """Check if this parser can handle the given data.

        Args:
            data: Raw file bytes.
            filename: Original filename (for heuristics).

        Returns:
            True if this parser can handle the data.
        """
        ...

    @abstractmethod
    def parse(self, data: bytes, filename: str = "") -> VendorBiosInfo:
        """Parse a vendor BIOS image and extract regions.

        Args:
            data: Raw file bytes.
            filename: Original filename.

        Returns:
            VendorBiosInfo with extracted data.

        Raises:
            ValueError: If the data cannot be parsed.
        """
        ...
