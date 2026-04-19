"""External tool manager.

Manages discovery and invocation of open source tools that biosforge
integrates with. All tools live inside the project's tools/ directory
(cloned by setup_tools.py). GPL tools are invoked as subprocesses
to maintain BSD-2 license compatibility.

Supported tools:
    - UEFIExtract   (BSD-2) - UEFI firmware extraction
    - UEFIFind      (BSD-2) - Pattern/GUID search in firmware
    - MEAnalyzer    (BSD-2) - Intel ME/CSME/TXE firmware analysis
    - MCExtractor   (BSD-2) - Intel/AMD/VIA microcode extraction
    - BIOSUtilities (BSD-2) - Vendor BIOS capsule extraction
    - me_cleaner    (GPL-3) - Intel ME cleaning (subprocess only)
    - ifdtool       (GPL-2) - Intel Flash Descriptor manipulation (subprocess only)
    - flashrom      (GPL-2) - SPI flash read/write (subprocess only)
"""

import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ToolLicense(Enum):
    BSD2 = "BSD-2-Clause"
    GPL2 = "GPL-2.0"
    GPL3 = "GPL-3.0"


@dataclass
class ToolInfo:
    """Metadata about an external tool."""
    name: str
    description: str
    license: ToolLicense
    repo_url: str
    # Relative path inside tools/ directory (set during discovery)
    rel_path: str
    is_python: bool = False  # True if it's a .py script
    path: Optional[Path] = None  # Absolute discovered path
    version: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.path is not None and self.path.exists()

    @property
    def is_gpl(self) -> bool:
        return self.license in (ToolLicense.GPL2, ToolLicense.GPL3)


_EXT = ".exe" if platform.system() == "Windows" else ""

# Registry: exact paths relative to tools/ directory
TOOL_REGISTRY: dict[str, ToolInfo] = {
    "uefiextract": ToolInfo(
        name="UEFIExtract",
        description="Extract UEFI firmware components to directory tree",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/LongSoft/UEFITool",
        rel_path=f"UEFITool/UEFIExtract{_EXT}",
    ),
    "uefifind": ToolInfo(
        name="UEFIFind",
        description="Search for patterns/GUIDs in UEFI firmware",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/LongSoft/UEFITool",
        rel_path=f"UEFITool/UEFIFind{_EXT}",
    ),
    "meanalyzer": ToolInfo(
        name="ME Analyzer",
        description="Intel ME/CSME/TXE firmware analysis",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/platomav/MEAnalyzer",
        rel_path="MEAnalyzer/MEA.py",
        is_python=True,
    ),
    "mcextractor": ToolInfo(
        name="MCExtractor",
        description="Intel/AMD/VIA microcode extraction and analysis",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/platomav/MCExtractor",
        rel_path="MCExtractor/MCE.py",
        is_python=True,
    ),
    "biosutilities": ToolInfo(
        name="BIOSUtilities",
        description="Vendor BIOS capsule extraction (AMI, Insyde, Phoenix)",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/platomav/BIOSUtilities",
        rel_path="BIOSUtilities/main.py",
        is_python=True,
    ),
    "me_cleaner": ToolInfo(
        name="me_cleaner",
        description="Clean/reduce Intel ME firmware (GPL - subprocess only)",
        license=ToolLicense.GPL3,
        repo_url="https://github.com/corna/me_cleaner",
        rel_path="me_cleaner/me_cleaner.py",
        is_python=True,
    ),
    "ifdtool": ToolInfo(
        name="ifdtool",
        description="Intel Flash Descriptor tool from coreboot (GPL - subprocess only)",
        license=ToolLicense.GPL2,
        repo_url="https://github.com/coreboot/coreboot/tree/main/util/ifdtool",
        rel_path=f"ifdtool/ifdtool{_EXT}",
    ),
    "flashrom": ToolInfo(
        name="flashrom",
        description="Universal SPI flash programmer (GPL - subprocess only)",
        license=ToolLicense.GPL2,
        repo_url="https://github.com/flashrom/flashrom",
        rel_path=f"flashrom/flashrom{_EXT}",
    ),
}


class ToolManager:
    """Discovers and manages external tools.

    All tools are searched ONLY inside the project's tools/ directory.
    No system PATH or external locations are checked.
    """

    def __init__(self, tools_dir: Optional[Path] = None):
        if tools_dir is None:
            tools_dir = Path(__file__).parent.parent.parent / "tools"
        self.tools_dir = tools_dir
        self._tools = {k: ToolInfo(**{f.name: getattr(v, f.name)
                        for f in v.__dataclass_fields__.values()})
                       for k, v in TOOL_REGISTRY.items()}
        self._discovered = False

    def discover_all(self) -> dict[str, ToolInfo]:
        """Discover tools inside tools/ directory only."""
        for key, tool in self._tools.items():
            candidate = self.tools_dir / tool.rel_path
            tool.path = candidate if candidate.exists() else None
        self._discovered = True
        return self._tools

    def get(self, name: str) -> Optional[ToolInfo]:
        if not self._discovered:
            self.discover_all()
        return self._tools.get(name)

    def get_available(self) -> dict[str, ToolInfo]:
        if not self._discovered:
            self.discover_all()
        return {k: v for k, v in self._tools.items() if v.available}

    def get_missing(self) -> dict[str, ToolInfo]:
        if not self._discovered:
            self.discover_all()
        return {k: v for k, v in self._tools.items() if not v.available}

    def run(self, tool_key: str, args: list[str],
            timeout: int = 120, capture: bool = True) -> subprocess.CompletedProcess:
        """Run an external tool as a subprocess."""
        tool = self.get(tool_key)
        if tool is None or not tool.available:
            raise FileNotFoundError(
                f"Tool '{tool_key}' not found in {self.tools_dir}. "
                f"Run setup_tools.py or download from: "
                f"{TOOL_REGISTRY[tool_key].repo_url}"
            )

        if tool.is_python:
            cmd = ["python", str(tool.path)] + args
        else:
            cmd = [str(tool.path)] + args

        return subprocess.run(
            cmd, capture_output=capture, text=True, timeout=timeout,
        )

    # ── Convenience runners ─────────────────────────────────────────

    def run_meanalyzer(self, firmware_path: str) -> Optional[str]:
        """Run ME Analyzer and return raw stdout."""
        try:
            result = self.run("meanalyzer", [firmware_path, "-skip"])
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def run_meanalyzer_parsed(self, firmware_path: str) -> Optional[dict]:
        """Run ME Analyzer and parse key fields from output.

        Returns dict with keys: version, sku, date, platform, type, etc.
        Returns None if MEA is not available.
        """
        raw = self.run_meanalyzer(firmware_path)
        if raw is None:
            return None
        return _parse_mea_output(raw)

    def run_mcextractor(self, firmware_path: str) -> Optional[str]:
        """Run MCExtractor and return raw stdout."""
        try:
            result = self.run("mcextractor", [firmware_path, "-skip"])
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def run_mcextractor_parsed(self, firmware_path: str) -> Optional[list[dict]]:
        """Run MCExtractor and parse microcode entries.

        Returns list of dicts with keys: cpuid, version, date, size.
        Returns None if MCExtractor is not available.
        """
        raw = self.run_mcextractor(firmware_path)
        if raw is None:
            return None
        return _parse_mce_output(raw)

    def run_me_cleaner(self, input_path: str, output_path: str,
                       soft_disable: bool = True) -> Optional[str]:
        """Run me_cleaner on an SPI image (GPL - subprocess)."""
        args = ["-O", output_path]
        if soft_disable:
            args.append("-S")
        args.append(input_path)
        try:
            result = self.run("me_cleaner", args)
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def run_uefiextract(self, firmware_path: str,
                        output_dir: Optional[str] = None) -> Optional[str]:
        """Run UEFIExtract on a firmware file."""
        args = [firmware_path]
        if output_dir:
            args.extend(["-o", output_dir])
        try:
            result = self.run("uefiextract", args)
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def run_ifdtool(self, firmware_path: str, dump_info: bool = True) -> Optional[str]:
        """Run ifdtool to analyze flash descriptor (GPL - subprocess)."""
        args = ["-d" if dump_info else "-x", firmware_path]
        try:
            result = self.run("ifdtool", args)
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def status_report(self) -> str:
        """Generate a human-readable status report of all tools."""
        if not self._discovered:
            self.discover_all()

        lines = ["External Tools Status:", f"  Tools directory: {self.tools_dir}", ""]
        for key, tool in self._tools.items():
            marker = "[+]" if tool.available else "[-]"
            gpl = " [GPL]" if tool.is_gpl else ""
            lines.append(f"  {marker} {tool.name}{gpl}: "
                         f"{'OK' if tool.available else 'NOT FOUND'}")
            if tool.available:
                lines.append(f"      {tool.path}")
            else:
                lines.append(f"      Expected: tools/{tool.rel_path}")
                lines.append(f"      Get it: {tool.repo_url}")
        return "\n".join(lines)


# ── Output parsers ──────────────────────────────────────────────────

def _parse_mea_output(raw: str) -> dict:
    """Parse ME Analyzer stdout into structured data."""
    result: dict = {"raw": raw}
    patterns = {
        "version": r"(?:ME|CSME|TXE|SPS)\s+Firmware\s+Version\s*:\s*(.+)",
        "sku": r"SKU\s*:\s*(.+)",
        "date": r"Date\s*:\s*(.+)",
        "platform": r"Platform\s*:\s*(.+)",
        "type": r"Type\s*:\s*(.+)",
        "release": r"Release\s*:\s*(.+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            result[key] = m.group(1).strip()
    return result


def _parse_mce_output(raw: str) -> list[dict]:
    """Parse MCExtractor stdout into list of microcode entries."""
    entries = []
    # MCE outputs lines like:
    #   CPUID: 0x000806EA  Version: 0x000000D6  Date: 2019-10-03  Size: 0x...
    for line in raw.splitlines():
        entry: dict = {}
        cpuid_m = re.search(r"CPUID\s*[:=]\s*(0x[0-9A-Fa-f]+)", line)
        ver_m = re.search(r"Version\s*[:=]\s*(0x[0-9A-Fa-f]+)", line)
        date_m = re.search(r"Date\s*[:=]\s*(\d{4}-\d{2}-\d{2})", line)
        size_m = re.search(r"Size\s*[:=]\s*(0x[0-9A-Fa-f]+|\d+)", line)
        if cpuid_m:
            entry["cpuid"] = cpuid_m.group(1)
        if ver_m:
            entry["version"] = ver_m.group(1)
        if date_m:
            entry["date"] = date_m.group(1)
        if size_m:
            entry["size"] = size_m.group(1)
        if entry.get("cpuid"):
            entries.append(entry)
    return entries
