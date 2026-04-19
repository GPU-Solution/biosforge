# biosforge

Open source UEFI/BIOS firmware reconstruction toolkit.

Rebuild flashable SPI images from programmer dumps + vendor BIOS updates + clean ME regions.

## Features

- **Flash Descriptor parser** — Intel IFD region detection and validation
- **ME region analysis** — $FPT partition table, version detection
- **Vendor BIOS extraction** — Auto-detect and extract BIOS from vendor update files
- **Image builder** — Combine regions from different sources into a flashable binary
- **External tools integration** — UEFITool, ME Analyzer, me_cleaner, ifdtool, flashrom
- **GUI + CLI** — Use whichever you prefer

### Supported vendors

- **HP** (softpaq .bin files)
- **Dell** (PFS update .exe files, via BIOSUtilities)
- Lenovo (planned)
- Asus (planned)

## Quick start

### CLI

```bash
# Analyze a dump
python -m biosforge.cli info dump.bin

# Build flashable image
python -m biosforge.cli build \
  --dump dump.bin \
  --bios Q85_013100.bin \
  --me clean_me.bin \
  -o flashable.bin

# Check external tools
python -m biosforge.cli tools
```

### GUI

```bash
python main.py
```

## How it works

1. **Load a programmer dump** — Full SPI flash read from the chip (CH341a, SVOD, etc.)
2. **Load a vendor BIOS update** — Downloaded from the manufacturer's website
3. **Optionally load a clean ME** — Full SPI dump with a known-good ME region
4. **Build** — biosforge extracts the BIOS region from the vendor file, the ME from the clean source, and the descriptor from your dump, then combines them into a flashable image

```
Output = Descriptor(dump) + ME(clean) + BIOS(vendor)
```

## External tools

biosforge integrates with these open source tools (invoke as subprocesses for GPL compatibility):

| Tool | License | Use |
|------|---------|-----|
| [UEFITool](https://github.com/LongSoft/UEFITool) | BSD-2 | UEFI firmware analysis |
| [ME Analyzer](https://github.com/platomav/MEAnalyzer) | BSD-2 | Intel ME analysis |
| [me_cleaner](https://github.com/corna/me_cleaner) | GPL-3 | ME cleaning |
| [ifdtool](https://github.com/coreboot/coreboot) | GPL-2 | Flash descriptor tool |
| [flashrom](https://github.com/flashrom/flashrom) | GPL-2 | SPI flash read/write |
| [BIOSUtilities](https://github.com/platomav/BIOSUtilities) | BSD-2 | Vendor capsule extraction |

## Requirements

- Python 3.10+
- tkinter (included with Python on Windows)
- No external pip dependencies for core functionality

## License

BSD-2-Clause
