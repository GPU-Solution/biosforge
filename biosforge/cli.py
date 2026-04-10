"""biosforge CLI interface.

Usage:
    biosforge build --dump DUMP --bios VENDOR_BIOS [--me CLEAN_ME] -o OUTPUT
    biosforge info DUMP
    biosforge tools
"""

import argparse
import os
import sys
from pathlib import Path

from .core.flash_descriptor import parse_descriptor, has_descriptor
from .core.me_parser import parse_me_region
from .core.builder import ImageBuilder
from .core.external_tools import ToolManager
from .vendors.registry import detect_vendor


def cmd_info(args):
    """Show information about a firmware image."""
    data = Path(args.file).read_bytes()
    fname = os.path.basename(args.file)
    print(f"File: {fname} ({len(data):,} bytes)")
    print()

    if has_descriptor(data):
        desc = parse_descriptor(data)
        print(desc.summary())
        print()

        # Parse ME if present
        me = desc.me_region
        if me and me.enabled:
            try:
                me_data = data[me.base:me.limit + 1]
                me_info = parse_me_region(me_data, me.base)
                print(me_info.summary())
            except ValueError as e:
                print(f"ME parse error: {e}")
    else:
        # Try vendor detection
        info = detect_vendor(data, fname)
        if info:
            print(info.summary())
        else:
            print("Not a recognized firmware format.")


def cmd_build(args):
    """Build a flashable image."""
    # Load dump
    dump_data = Path(args.dump).read_bytes()
    dump_name = os.path.basename(args.dump)
    print(f"Dump: {dump_name} ({len(dump_data):,} bytes)")

    if not has_descriptor(dump_data):
        print("ERROR: Dump has no valid Intel Flash Descriptor.", file=sys.stderr)
        sys.exit(1)

    builder = ImageBuilder(dump_data, dump_name)
    desc = builder.descriptor

    # Load vendor BIOS
    vendor_data = Path(args.bios).read_bytes()
    vendor_name = os.path.basename(args.bios)
    info = detect_vendor(vendor_data, vendor_name)

    if info is None:
        print(f"ERROR: Could not detect vendor format for {vendor_name}", file=sys.stderr)
        sys.exit(1)

    print(f"Vendor: {info.vendor} {info.version} (BIOS: {len(info.bios_data):,} bytes)")

    bios_region = desc.bios_region
    if bios_region and info.has_bios:
        bios_data = info.bios_data
        if len(bios_data) != bios_region.size:
            if len(bios_data) < bios_region.size:
                bios_data = bios_data + b"\xff" * (bios_region.size - len(bios_data))
                print(f"  (padded BIOS to {len(bios_data):,} bytes)")
            else:
                bios_data = bios_data[:bios_region.size]
                print(f"  (truncated BIOS to {len(bios_data):,} bytes)")
        builder.set_bios(bios_data, f"{info.vendor} {info.version}")

    # Load clean ME (optional)
    if args.me:
        me_source = Path(args.me).read_bytes()
        me_name = os.path.basename(args.me)
        print(f"ME source: {me_name} ({len(me_source):,} bytes)")

        if has_descriptor(me_source):
            me_desc = parse_descriptor(me_source)
            me_region_src = me_desc.me_region
            me_region_dst = desc.me_region
            if (me_region_src and me_region_dst
                    and me_region_src.enabled and me_region_dst.enabled):
                me_raw = me_source[me_region_src.base:me_region_src.limit + 1]
                if len(me_raw) == me_region_dst.size:
                    builder.set_me(me_raw, me_name)
                    print(f"  ME region: {len(me_raw):,} bytes")
                else:
                    print(f"  WARNING: ME size mismatch ({len(me_raw)} vs {me_region_dst.size})")
        else:
            print("  WARNING: ME source has no flash descriptor, skipping")

    # Build
    print()
    result = builder.build()
    print(result.summary())

    # Save
    output = args.output
    result.save(output)
    print(f"\nSaved: {output}")


def cmd_tools(args):
    """Show external tools status."""
    tm = ToolManager()
    tm.discover_all()
    print(tm.status_report())


def main():
    parser = argparse.ArgumentParser(
        prog="biosforge",
        description="Open source UEFI/BIOS firmware reconstruction toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    # info
    p_info = sub.add_parser("info", help="Show firmware image info")
    p_info.add_argument("file", help="Firmware image file")

    # build
    p_build = sub.add_parser("build", help="Build flashable image")
    p_build.add_argument("--dump", "-d", required=True, help="Programmer dump file")
    p_build.add_argument("--bios", "-b", required=True, help="Vendor BIOS image")
    p_build.add_argument("--me", "-m", help="Clean ME source (full SPI dump)")
    p_build.add_argument("--output", "-o", default="flashable_output.bin",
                         help="Output file path")

    # tools
    sub.add_parser("tools", help="Show external tools status")

    args = parser.parse_args()

    if args.command == "info":
        cmd_info(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "tools":
        cmd_tools(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
