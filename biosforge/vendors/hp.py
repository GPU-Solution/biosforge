"""HP BIOS image parser.

Parses HP softpaq .bin files extracted by HpFirmwareUpdRec.exe.
These files contain BIOS + optional partial ME, prefixed by a small header.

Tested with:
    - HP ProBook 440 G5 (Q85_013100.bin)

Format:
    [header: 0x220 bytes] [BIOS region: N bytes] [ME data: optional]

The header size is detected by aligning the first EFI Firmware Volume
(_FVH signature) with the expected offset within the BIOS region.
"""

import struct
from typing import Optional

from .base import VendorParser, VendorBiosInfo


# EFI Firmware Volume signature at offset +0x28 in volume header
FVH_SIGNATURE = b"_FVH"

# ME Flash Partition Table signature
FPT_SIGNATURE = b"$FPT"


class HPParser(VendorParser):
    """Parser for HP softpaq BIOS .bin files."""

    @property
    def vendor_name(self) -> str:
        return "HP"

    def can_parse(self, data: bytes, filename: str = "") -> bool:
        """Detect HP BIOS .bin format.

        Heuristics:
        1. File is > 1 MB
        2. No Intel Flash Descriptor at offset 0x10
        3. Contains _FVH signature within first 1 MB
        4. Filename matches Q*.bin or similar HP pattern
        """
        if len(data) < 1024 * 1024:
            return False

        # Must NOT have a flash descriptor (that would be a full dump)
        if len(data) >= 0x14:
            sig = struct.unpack_from("<I", data, 0x10)[0]
            if sig == 0x0FF0A55A:
                return False

        # Must contain at least one EFI FV
        if FVH_SIGNATURE not in data[:1024 * 1024]:
            return False

        # Filename hint
        fn = filename.upper()
        if fn.endswith(".BIN"):
            # HP naming: Q85_013100.bin, R70_010600.bin, etc.
            name = fn[:-4]
            if "_" in name and len(name) <= 20:
                return True

        # Even without filename match, if it has FVH and no descriptor,
        # it's likely an HP/vendor BIOS bin
        return True

    def parse(self, data: bytes, filename: str = "") -> VendorBiosInfo:
        """Parse HP BIOS .bin and extract BIOS + optional ME regions.

        The key challenge is detecting the header size. We do this by
        finding the first _FVH signature and computing the offset.
        """
        info = VendorBiosInfo(vendor="HP", total_size=len(data))

        # Extract model identifier from filename
        if filename:
            name = filename.rsplit(".", 1)[0] if "." in filename else filename
            info.version = name
            # Q85 -> ProBook 440 G5 series, etc.
            model_code = name.split("_")[0] if "_" in name else name
            info.model = model_code

        # Detect header size by finding first _FVH
        header_size = self._detect_header_size(data)
        if header_size is None:
            raise ValueError("Could not detect HP BIOS header size")
        info.header_size = header_size

        # Extract everything after header as BIOS data.
        # The HP .bin may also contain partial ME data after the BIOS region,
        # but we don't split it here — the builder will truncate to the
        # exact BIOS region size from the dump's flash descriptor.
        info.bios_data = data[header_size:]
        info.notes.append(f"Header: {header_size} bytes (0x{header_size:X})")
        info.notes.append(
            "Raw data after header includes BIOS + possible ME tail. "
            "Builder will use only what fits the BIOS region."
        )

        return info

    def _detect_header_size(self, data: bytes) -> Optional[int]:
        """Detect the header size before the BIOS region data.

        Strategy: Find the first _FVH signature. In a standard UEFI BIOS
        region, the first FV typically starts at a well-known offset
        (often 0x3C000 for 9MB HP BIOS regions). The header size is
        the difference between the _FVH position in the file and
        its expected position in a headerless image.
        """
        # Find first _FVH in the file
        first_fvh = self._find_first_fvh(data)
        if first_fvh is None:
            return None

        # The FV header starts 0x28 bytes before _FVH
        first_fv_offset = first_fvh - 0x28
        if first_fv_offset < 0:
            return None

        # Common header sizes for HP bins
        # Try each and check if the data alignment makes sense
        for candidate_header in [0x220, 0x200, 0x100, 0x0]:
            fv_in_bios = first_fv_offset - candidate_header
            # The first FV in BIOS region is usually at a 0x1000-aligned offset
            if fv_in_bios >= 0 and fv_in_bios % 0x1000 == 0:
                return candidate_header

        # Fallback: check if first 0x220 bytes are mostly zeros
        if first_fv_offset >= 0x220:
            header_candidate = data[:0x220]
            non_zero = sum(1 for b in header_candidate if b != 0x00 and b != 0xFF)
            if non_zero < 100:  # Mostly padding
                return 0x220

        # Last resort: assume no header
        return 0

    def _find_first_fvh(self, data: bytes) -> Optional[int]:
        """Find the first _FVH signature in the data."""
        # Search in the first few MB
        search_limit = min(len(data), 4 * 1024 * 1024)
        pos = 0
        while pos < search_limit:
            idx = data.find(FVH_SIGNATURE, pos)
            if idx == -1:
                break
            # Validate: the FV header should have reasonable values
            fv_start = idx - 0x28
            if fv_start >= 0:
                fv_length = struct.unpack_from("<Q", data, fv_start + 0x20)[0]
                # Sanity: FV should be between 4KB and 16MB
                if 0x1000 <= fv_length <= 0x1000000:
                    return idx
            pos = idx + 1
        return None

    def _find_me_boundary(self, data: bytes, header_size: int) -> Optional[int]:
        """Find where ME data starts in the image (after BIOS).

        The ME data (if present) follows the BIOS region and starts
        with boot code followed by $FPT.
        """
        # Search for $FPT after the first MB of data
        search_start = max(header_size + 1024 * 1024, len(data) // 2)

        pos = search_start
        while pos < len(data) - 4:
            idx = data.find(FPT_SIGNATURE, pos)
            if idx == -1:
                break

            # $FPT should be preceded by some boot code or zeros
            # The ME region usually starts at a page-aligned offset
            # relative to the BIOS start
            me_start_candidate = idx
            # Walk back to find the actual start (usually 0x10-0x250 before $FPT)
            for back_offset in [0x250, 0x10, 0x0]:
                candidate = idx - back_offset
                if candidate >= header_size:
                    # Check if this offset is aligned relative to BIOS
                    bios_relative = candidate - header_size
                    if bios_relative % 0x1000 == 0:
                        return candidate

            # Fallback: round down to nearest 0x1000 alignment
            aligned = (idx // 0x1000) * 0x1000
            if aligned >= header_size:
                return aligned

            pos = idx + 4

        return None


def detect_hp_bios(data: bytes, filename: str = "") -> Optional[VendorBiosInfo]:
    """Convenience function to parse HP BIOS if detected."""
    parser = HPParser()
    if parser.can_parse(data, filename):
        return parser.parse(data, filename)
    return None
