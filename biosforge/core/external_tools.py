"""External tool manager.

Manages discovery, download, and invocation of open source tools that
biosforge integrates with. All GPL tools are invoked as subprocesses
to maintain BSD-2 license compatibility.

Supported tools:
    - UEFIExtract (BSD-2) - UEFI firmware extraction
    - UEFIFind   (BSD-2) - Pattern/GUID search in firmware
    - MEAnalyzer (BSD-2) - Intel ME firmware analysis
    - me_cleaner (GPL-3) - Intel ME cleaning (subprocess only)
    - ifdtool    (GPL-2) - Intel Flash Descriptor manipulation (subprocess only)
    - flashrom   (GPL-2) - SPI flash read/write (subprocess only)
"""

import json
import os
import platform
import shutil
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
    binary_name: str  # Expected executable name
    python_module: Optional[str] = None  # If it's a Python tool
    path: Optional[Path] = None  # Discovered path on this system
    version: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.path is not None

    @property
    def is_gpl(self) -> bool:
        return self.license in (ToolLicense.GPL2, ToolLicense.GPL3)


# Registry of all supported external tools
TOOL_REGISTRY: dict[str, ToolInfo] = {
    "uefiextract": ToolInfo(
        name="UEFIExtract",
        description="Extract UEFI firmware components to directory tree",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/LongSoft/UEFITool",
        binary_name="UEFIExtract.exe" if platform.system() == "Windows" else "UEFIExtract",
    ),
    "uefifind": ToolInfo(
        name="UEFIFind",
        description="Search for patterns/GUIDs in UEFI firmware",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/LongSoft/UEFITool",
        binary_name="UEFIFind.exe" if platform.system() == "Windows" else "UEFIFind",
    ),
    "meanalyzer": ToolInfo(
        name="ME Analyzer",
        description="Intel ME/CSME/TXE firmware analysis",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/platomav/MEAnalyzer",
        binary_name="MEA.py",
        python_module="MEA",
    ),
    "me_cleaner": ToolInfo(
        name="me_cleaner",
        description="Clean/reduce Intel ME firmware (GPL - subprocess only)",
        license=ToolLicense.GPL3,
        repo_url="https://github.com/corna/me_cleaner",
        binary_name="me_cleaner.py",
        python_module="me_cleaner",
    ),
    "ifdtool": ToolInfo(
        name="ifdtool",
        description="Intel Flash Descriptor tool from coreboot (GPL - subprocess only)",
        license=ToolLicense.GPL2,
        repo_url="https://github.com/coreboot/coreboot/tree/main/util/ifdtool",
        binary_name="ifdtool.exe" if platform.system() == "Windows" else "ifdtool",
    ),
    "flashrom": ToolInfo(
        name="flashrom",
        description="Universal SPI flash programmer (GPL - subprocess only)",
        license=ToolLicense.GPL2,
        repo_url="https://github.com/flashrom/flashrom",
        binary_name="flashrom.exe" if platform.system() == "Windows" else "flashrom",
    ),
    "biosutilities": ToolInfo(
        name="BIOSUtilities",
        description="Vendor BIOS capsule extraction (AMI, Insyde, Phoenix)",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/platomav/BIOSUtilities",
        binary_name="",
        python_module="biosutilities",
    ),
    "mcextractor": ToolInfo(
        name="MCExtractor",
        description="Intel/AMD/VIA microcode extraction and analysis",
        license=ToolLicense.BSD2,
        repo_url="https://github.com/platomav/MCExtractor",
        binary_name="MCE.py",
        python_module="MCE",
    ),
}


class ToolManager:
    """Discovers and manages external tools."""

    def __init__(self, tools_dir: Optional[Path] = None):
        """Initialize tool manager.

        Args:
            tools_dir: Directory where bundled tools are stored.
                      Defaults to <biosforge_dir>/tools/
        """
        if tools_dir is None:
            tools_dir = Path(__file__).parent.parent.parent / "tools"
        self.tools_dir = tools_dir
        self._tools = dict(TOOL_REGISTRY)
        self._discovered = False

    def discover_all(self) -> dict[str, ToolInfo]:
        """Discover all available tools on the system.

        Searches in order:
        1. Bundled tools directory
        2. System PATH
        3. Common installation locations
        """
        for key, tool in self._tools.items():
            tool.path = self._find_tool(tool)
            if tool.path:
                tool.version = self._get_version(tool)

        self._discovered = True
        return self._tools

    def get(self, name: str) -> Optional[ToolInfo]:
        """Get tool info by registry key."""
        if not self._discovered:
            self.discover_all()
        return self._tools.get(name)

    def get_available(self) -> dict[str, ToolInfo]:
        """Get all available (discovered) tools."""
        if not self._discovered:
            self.discover_all()
        return {k: v for k, v in self._tools.items() if v.available}

    def get_missing(self) -> dict[str, ToolInfo]:
        """Get all tools that were not found."""
        if not self._discovered:
            self.discover_all()
        return {k: v for k, v in self._tools.items() if not v.available}

    def run(self, tool_key: str, args: list[str],
            timeout: int = 120, capture: bool = True) -> subprocess.CompletedProcess:
        """Run an external tool as a subprocess.

        This is the primary method for invoking GPL tools to maintain
        license separation.

        Args:
            tool_key: Key from TOOL_REGISTRY.
            args: Command line arguments.
            timeout: Max execution time in seconds.
            capture: Capture stdout/stderr.

        Returns:
            CompletedProcess with stdout/stderr.

        Raises:
            FileNotFoundError: If tool is not available.
            subprocess.TimeoutExpired: If tool exceeds timeout.
        """
        tool = self.get(tool_key)
        if tool is None or not tool.available:
            raise FileNotFoundError(
                f"Tool '{tool_key}' not found. "
                f"Download from: {TOOL_REGISTRY[tool_key].repo_url}"
            )

        cmd = [str(tool.path)] + args

        # Python scripts need to be run via python interpreter
        if tool.python_module and str(tool.path).endswith(".py"):
            cmd = ["python3", str(tool.path)] + args

        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )

    def run_meanalyzer(self, firmware_path: str) -> Optional[str]:
        """Run ME Analyzer on a firmware file and return output."""
        try:
            result = self.run("meanalyzer", [firmware_path, "-skip"])
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def run_me_cleaner(self, input_path: str, output_path: str,
                       soft_disable: bool = True) -> Optional[str]:
        """Run me_cleaner on an SPI image (GPL - subprocess).

        Args:
            input_path: Path to input SPI image.
            output_path: Path for cleaned output.
            soft_disable: Use -S flag for soft disable (recommended).
        """
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

        lines = ["External Tools Status:", ""]
        for key, tool in self._tools.items():
            status = "OK" if tool.available else "NOT FOUND"
            marker = "[+]" if tool.available else "[-]"
            ver = f" (v{tool.version})" if tool.version else ""
            gpl = " [GPL]" if tool.is_gpl else ""
            lines.append(f"  {marker} {tool.name}{ver}{gpl}: {status}")
            if tool.available:
                lines.append(f"      Path: {tool.path}")
            else:
                lines.append(f"      Get it: {tool.repo_url}")
        return "\n".join(lines)

    def _find_tool(self, tool: ToolInfo) -> Optional[Path]:
        """Search for a tool binary/script."""
        if not tool.binary_name:
            # Python-only module, check import
            if tool.python_module:
                try:
                    __import__(tool.python_module)
                    return Path(tool.python_module)  # Placeholder
                except ImportError:
                    pass
            return None

        # 1. Check bundled tools directory
        bundled = self.tools_dir / tool.binary_name
        if bundled.exists():
            return bundled

        # 2. Check system PATH
        found = shutil.which(tool.binary_name)
        if found:
            return Path(found)

        # 3. Check common locations
        common_paths = self._get_common_paths(tool)
        for p in common_paths:
            if p.exists():
                return p

        return None

    def _get_common_paths(self, tool: ToolInfo) -> list[Path]:
        """Get common installation paths for a tool."""
        paths = []
        home = Path.home()

        if platform.system() == "Windows":
            # Check Desktop (where Lucas has MEA)
            desktop = home / "Escritorio"
            paths.append(desktop / "MEA" / tool.binary_name)
            paths.append(desktop / tool.binary_name)
            paths.append(home / "Desktop" / tool.binary_name)

            # Check Program Files
            for pf in ["C:/Program Files", "C:/Program Files (x86)"]:
                paths.append(Path(pf) / tool.name / tool.binary_name)
        else:
            paths.append(Path("/usr/local/bin") / tool.binary_name)
            paths.append(Path("/usr/bin") / tool.binary_name)
            paths.append(home / ".local" / "bin" / tool.binary_name)

        return paths

    def _get_version(self, tool: ToolInfo) -> Optional[str]:
        """Try to get the version of a discovered tool."""
        if not tool.path:
            return None
        try:
            result = subprocess.run(
                [str(tool.path), "--version"],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip() or result.stderr.strip()
            # Return first line, truncated
            if output:
                return output.split("\n")[0][:80]
        except Exception:
            pass
        return None
