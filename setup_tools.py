#!/usr/bin/env python3
"""Download and set up external tools into tools/ directory.

Usage:
    python setup_tools.py          # Clone/download all tools
    python setup_tools.py --status # Show status of tools
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

TOOLS_DIR = Path(__file__).parent / "tools"

# Tools to clone via git
GIT_REPOS = {
    "MEAnalyzer": {
        "url": "https://github.com/platomav/MEAnalyzer.git",
        "license": "BSD-2-Clause",
        "desc": "Intel ME/CSME/TXE firmware analysis",
    },
    "BIOSUtilities": {
        "url": "https://github.com/platomav/BIOSUtilities.git",
        "license": "Custom",
        "desc": "Vendor BIOS capsule extraction (AMI, Insyde, Phoenix)",
    },
    "MCExtractor": {
        "url": "https://github.com/platomav/MCExtractor.git",
        "license": "BSD-2-Clause",
        "desc": "Intel/AMD/VIA microcode extraction",
    },
    "me_cleaner": {
        "url": "https://github.com/corna/me_cleaner.git",
        "license": "GPL-3.0 (subprocess only)",
        "desc": "Intel ME cleaning/reduction",
    },
    "uefi-firmware-parser": {
        "url": "https://github.com/theopolis/uefi-firmware-parser.git",
        "license": "Custom",
        "desc": "Python UEFI firmware parser",
    },
    "chipsec": {
        "url": "https://github.com/chipsec/chipsec.git",
        "sparse": ["chipsec/hal/spi_descriptor.py", "chipsec/hal/spi.py"],
        "license": "GPL-2.0 (reference only)",
        "desc": "Platform security assessment (SPI descriptor reference)",
    },
}

# UEFITool releases (pre-built binaries)
UEFITOOL_RELEASE = "https://api.github.com/repos/LongSoft/UEFITool/releases/latest"


def run(cmd, **kwargs):
    """Run a command and return result."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def clone_repo(name, info):
    """Clone a git repository into tools/."""
    dest = TOOLS_DIR / name
    if dest.exists():
        print(f"  [skip] {name} already exists")
        # Pull latest
        result = run(["git", "-C", str(dest), "pull", "--ff-only"])
        if result.returncode == 0:
            print(f"  [updated] {name}")
        return True

    print(f"  [clone] {name} from {info['url']}")

    if "sparse" in info:
        # Sparse checkout - only get specific files
        dest.mkdir(parents=True, exist_ok=True)
        run(["git", "init", str(dest)])
        run(["git", "-C", str(dest), "remote", "add", "origin", info["url"]])
        run(["git", "-C", str(dest), "config", "core.sparseCheckout", "true"])
        sparse_file = dest / ".git" / "info" / "sparse-checkout"
        sparse_file.parent.mkdir(parents=True, exist_ok=True)
        sparse_file.write_text("\n".join(info["sparse"]) + "\n")
        result = run(["git", "-C", str(dest), "pull", "origin", "master"])
        if result.returncode != 0:
            run(["git", "-C", str(dest), "pull", "origin", "main"])
    else:
        result = run(["git", "clone", "--depth", "1", info["url"], str(dest)])

    if not dest.exists() or not any(dest.iterdir()):
        print(f"  [FAILED] {name}")
        return False

    print(f"  [OK] {name}")
    return True


def setup_uefitool():
    """Download UEFITool pre-built binaries."""
    dest = TOOLS_DIR / "UEFITool"
    dest.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    if system == "Windows":
        suffix = "win"
        ext = ".exe"
    elif system == "Linux":
        suffix = "linux"
        ext = ""
    elif system == "Darwin":
        suffix = "mac"
        ext = ""
    else:
        print(f"  [skip] UEFITool: unsupported platform {system}")
        return

    # Check if already present
    extract_bin = dest / f"UEFIExtract{ext}"
    find_bin = dest / f"UEFIFind{ext}"
    if extract_bin.exists() and find_bin.exists():
        print(f"  [skip] UEFITool binaries already present")
        return

    print(f"  [download] UEFITool binaries for {system}")
    print(f"  Note: Download latest release from https://github.com/LongSoft/UEFITool/releases")
    print(f"  Place UEFIExtract{ext} and UEFIFind{ext} in {dest}")


def setup_ifdtool():
    """Set up ifdtool from coreboot."""
    dest = TOOLS_DIR / "ifdtool"
    dest.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    ext = ".exe" if system == "Windows" else ""
    binary = dest / f"ifdtool{ext}"

    if binary.exists():
        print(f"  [skip] ifdtool binary already present")
        return

    print(f"  [info] ifdtool: needs to be compiled from coreboot source")
    print(f"  Source: https://github.com/coreboot/coreboot/tree/main/util/ifdtool")
    print(f"  Place compiled ifdtool{ext} in {dest}")


def setup_flashrom():
    """Set up flashrom."""
    dest = TOOLS_DIR / "flashrom"
    dest.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    ext = ".exe" if system == "Windows" else ""
    binary = dest / f"flashrom{ext}"

    if binary.exists():
        print(f"  [skip] flashrom binary already present")
        return

    print(f"  [info] flashrom: download pre-built binary")
    if system == "Windows":
        print(f"  Download from: https://flashrom.org/Flashrom/1.4.0")
    else:
        print(f"  Install via package manager: apt install flashrom / brew install flashrom")
    print(f"  Place flashrom{ext} in {dest}")


def show_status():
    """Show status of all tools."""
    print("External Tools Status:")
    print()

    for name, info in GIT_REPOS.items():
        dest = TOOLS_DIR / name
        exists = dest.exists() and any(dest.iterdir())
        marker = "[+]" if exists else "[-]"
        print(f"  {marker} {name:25s} {info['license']:20s} {info['desc']}")
        if exists:
            print(f"      Path: {dest}")
        else:
            print(f"      Clone: {info['url']}")

    print()
    # Check binaries
    system = platform.system()
    ext = ".exe" if system == "Windows" else ""
    binaries = {
        "UEFIExtract": TOOLS_DIR / "UEFITool" / f"UEFIExtract{ext}",
        "UEFIFind": TOOLS_DIR / "UEFITool" / f"UEFIFind{ext}",
        "ifdtool": TOOLS_DIR / "ifdtool" / f"ifdtool{ext}",
        "flashrom": TOOLS_DIR / "flashrom" / f"flashrom{ext}",
    }
    for name, path in binaries.items():
        exists = path.exists()
        marker = "[+]" if exists else "[-]"
        print(f"  {marker} {name:25s} {'binary':20s} {path}")


def main():
    parser = argparse.ArgumentParser(description="Setup biosforge external tools")
    parser.add_argument("--status", action="store_true", help="Show tools status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    print("Setting up biosforge external tools...")
    print(f"Target directory: {TOOLS_DIR}")
    print()

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    # Write .gitignore for tools dir (don't track cloned repos)
    gitignore = TOOLS_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# External tools - cloned by setup_tools.py\n*\n!.gitignore\n")

    # Clone Python tools
    print("=== Python tools (git clone) ===")
    for name, info in GIT_REPOS.items():
        clone_repo(name, info)
    print()

    # Pre-built binaries
    print("=== Pre-built binaries ===")
    setup_uefitool()
    setup_ifdtool()
    setup_flashrom()
    print()

    print("Done! Run 'python setup_tools.py --status' to check.")


if __name__ == "__main__":
    main()
