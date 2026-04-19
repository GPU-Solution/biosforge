"""Dell BIOS image parser.

Parses Dell PFS update .exe files by invoking BIOSUtilities DellPfsExtract
as a subprocess, then reading the extracted firmware components.

Extracted components typically include:
    - System BIOS (with or without BIOS Guard wrapper)
    - Embedded Controller (main + backup)
    - Intel ME update (FWUpdate format, not a raw region)
    - Integrated Sensor Hub (ISH)
    - Model Information text file

Tested with:
    - Dell Latitude 7400 (Latitude_7X00_1.43.0.exe)
"""

import os
import re
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Optional

from .base import VendorParser, VendorBiosInfo, ExtractedComponent


# Dell PFS signatures
PFS_HDR_SIGNATURE = b"PFS.HDR."
PFS_FTR_SIGNATURE = b"PFS.FTR."

# Patterns for identifying extracted components by filename
# BIOSUtilities names them like:
#   "1 ModelName -- 1 System BIOS with BIOS Guard v1.43.0.bin"
#   "1 ModelName -- 2 Embedded Controller v1.4.1.bin"
_RE_COMPONENT = re.compile(
    r"--\s*(\d+)\s+(.+?)\s+v([\d.]+)\.\w+$"
)


class DellParser(VendorParser):
    """Parser for Dell PFS BIOS update .exe files."""

    def __init__(self, biosutil_path: Optional[Path] = None):
        """Initialize Dell parser.

        Args:
            biosutil_path: Path to BIOSUtilities package directory.
                If None, tries to find it relative to biosforge project.
        """
        self._biosutil_path = biosutil_path

    @property
    def vendor_name(self) -> str:
        return "Dell"

    def can_parse(self, data: bytes, filename: str = "") -> bool:
        """Detect Dell PFS format.

        Heuristics:
        1. Contains PFS.HDR. signature (Dell PFS container)
        2. File is > 1 MB (BIOS updates are large)
        """
        if len(data) < 1024 * 1024:
            return False
        return PFS_HDR_SIGNATURE in data[:0x200000]

    def parse(self, data: bytes, filename: str = "") -> VendorBiosInfo:
        """Parse Dell PFS update and extract firmware components.

        Uses BIOSUtilities DellPfsExtract via subprocess for the heavy
        lifting (PFS container unpacking, decompression, signature
        stripping). Then reads and classifies the extracted files.
        """
        info = VendorBiosInfo(vendor="Dell", total_size=len(data))

        # Write input to temp file for BIOSUtilities
        tmp_dir = tempfile.mkdtemp(prefix="biosforge_dell_")
        input_file = os.path.join(tmp_dir, filename or "dell_update.exe")
        output_dir = os.path.join(tmp_dir, "extracted")

        try:
            Path(input_file).write_bytes(data)
            os.makedirs(output_dir, exist_ok=True)

            # Run BIOSUtilities DellPfsExtract
            extracted = self._run_extract(input_file, output_dir)
            if not extracted:
                raise ValueError(
                    "BIOSUtilities DellPfsExtract failed or not available. "
                    "Install BIOSUtilities in biosforge/tools/BIOSUtilities/"
                )

            # Find the Firmware subfolder
            firmware_dir = self._find_firmware_dir(output_dir)
            if firmware_dir is None:
                raise ValueError(
                    "No Firmware directory in DellPfsExtract output"
                )

            # Parse extracted files
            self._classify_components(info, firmware_dir)

            # Try to read Model Information
            self._read_model_info(info, firmware_dir)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return info

    def _run_extract(self, input_file: str, output_dir: str) -> bool:
        """Run BIOSUtilities DellPfsExtract as subprocess."""
        import subprocess

        biosutil = self._find_biosutilities()
        if biosutil is None:
            return False

        try:
            result = subprocess.run(
                [
                    "python", "-m", "biosutilities",
                    "-e", "-u", "DellPfsExtract",
                    "-o", output_dir,
                    input_file,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(biosutil),
            )
            # BIOSUtilities may return 0 even if extraction had issues,
            # so also check if output directory has content
            return any(Path(output_dir).rglob("*"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _find_biosutilities(self) -> Optional[Path]:
        """Locate BIOSUtilities package."""
        if self._biosutil_path and self._biosutil_path.exists():
            return self._biosutil_path

        # Try relative to biosforge project
        project_root = Path(__file__).parent.parent.parent
        candidates = [
            project_root / "tools" / "BIOSUtilities",
            project_root / "tools" / "biosutilities",
        ]
        for c in candidates:
            if (c / "biosutilities").is_dir() or (c / "__main__.py").exists():
                return c
        return None

    def _find_firmware_dir(self, output_dir: str) -> Optional[Path]:
        """Find the Firmware subdirectory in extraction output.

        BIOSUtilities creates: output/<filename>_extracted/Firmware/
        """
        out = Path(output_dir)
        if not out.exists():
            return None

        # Walk one or two levels deep looking for "Firmware" dir
        for root, dirs, _files in os.walk(out):
            if "Firmware" in dirs:
                return Path(root) / "Firmware"
            # Don't recurse too deep
            depth = str(Path(root)).count(os.sep) - str(out).count(os.sep)
            if depth >= 2:
                break
        return None

    def _classify_components(self, info: VendorBiosInfo, firmware_dir: Path) -> None:
        """Read extracted files and classify into BIOS, EC, ME, etc."""
        ec_main_seen = False

        for fpath in sorted(firmware_dir.iterdir()):
            if not fpath.is_file():
                continue

            fname = fpath.name
            match = _RE_COMPONENT.search(fname)
            if not match:
                continue

            idx = int(match.group(1))
            name = match.group(2).strip()
            version = match.group(3)
            file_data = fpath.read_bytes()

            component = ExtractedComponent(
                name=name,
                data=file_data,
                version=version,
                filename=fname,
            )
            info.components.append(component)

            name_lower = name.lower()

            # System BIOS
            if "system bios" in name_lower:
                info.bios_data = file_data
                info.version = version
                info.notes.append(
                    f"BIOS: {name} v{version} "
                    f"({len(file_data):,} bytes)"
                )

            # Embedded Controller (first = main, second = backup)
            elif "embedded controller" in name_lower:
                if "backup" in name_lower:
                    info.ec_backup_data = file_data
                elif not ec_main_seen:
                    info.ec_data = file_data
                    ec_main_seen = True
                    info.notes.append(
                        f"EC: v{version} ({len(file_data):,} bytes)"
                    )
                # Dell sometimes has two identical EC pairs (two flash chips)
                # We take the first main + first backup

            # Intel ME update (prefer VPro/larger variant)
            elif "management engine" in name_lower:
                is_vpro = "vpro" in name_lower and "non-vpro" not in name_lower
                me_type = "VPro" if is_vpro else "Non-VPro"
                # Only store if we don't have one yet, or this one is VPro
                if info.me_data is None or is_vpro:
                    info.me_data = file_data
                info.notes.append(
                    f"ME update ({me_type}): v{version} "
                    f"({len(file_data):,} bytes) [FWUpdate format]"
                )

            # ISH, TI Port Controller, etc. - stored as components only

    def _read_model_info(self, info: VendorBiosInfo, firmware_dir: Path) -> None:
        """Read Dell Model Information text file if present."""
        for fpath in firmware_dir.iterdir():
            if "model information" in fpath.name.lower() and fpath.suffix == ".txt":
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        if line.startswith("SystemName="):
                            info.model = line.split("=", 1)[1].strip()
                        elif line.startswith("Version=") and not info.version:
                            info.version = line.split("=", 1)[1].strip()
                except OSError:
                    pass
                break


def detect_dell_bios(data: bytes, filename: str = "") -> Optional[VendorBiosInfo]:
    """Convenience function to parse Dell BIOS if detected."""
    parser = DellParser()
    if parser.can_parse(data, filename):
        return parser.parse(data, filename)
    return None
