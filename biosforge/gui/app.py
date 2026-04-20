"""biosforge GUI - Main application window.

Provides a tkinter-based interface for:
1. Loading a programmer dump (SPI flash image)
2. Loading a vendor BIOS update (HP, Dell, etc.)
3. Loading a clean ME image
4. Viewing region layout and metadata
5. Building a flashable image
6. Running external tools (MEA, UEFIExtract, etc.)
"""

import hashlib
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from biosforge.core.flash_descriptor import (
    parse_descriptor, has_descriptor, FlashDescriptor, RegionType,
)
from biosforge.core.me_parser import parse_me_region, MEInfo
from biosforge.core.builder import ImageBuilder, BuildResult
from biosforge.core.regions import extract_all_regions, ExtractedRegion
from biosforge.core.external_tools import ToolManager
from biosforge.vendors.registry import detect_vendor
from biosforge.vendors.base import VendorBiosInfo


class BiosForgeApp:
    """Main application class."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("biosforge v0.2.0-alpha — SPI Flash Reconstruction Toolkit")
        self.root.geometry("1000x750")
        self.root.minsize(850, 600)

        # State
        self.dump_data: Optional[bytes] = None
        self.dump_path: Optional[str] = None
        self.dump_descriptor: Optional[FlashDescriptor] = None
        self.dump_me_info: Optional[MEInfo] = None

        self.vendor_data: Optional[bytes] = None
        self.vendor_path: Optional[str] = None
        self.vendor_info: Optional[VendorBiosInfo] = None

        self.me_data: Optional[bytes] = None
        self.me_path: Optional[str] = None
        self.me_descriptor: Optional[FlashDescriptor] = None
        self.me_info: Optional[MEInfo] = None

        self.last_build: Optional[BuildResult] = None

        # Tools
        self.tools = ToolManager()

        self._build_ui()
        self._check_tools()

    def run(self):
        self.root.mainloop()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self):
        # Menu bar
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Dump...", command=self._load_dump,
                              accelerator="Ctrl+D")
        file_menu.add_command(label="Open Vendor BIOS...", command=self._load_vendor,
                              accelerator="Ctrl+B")
        file_menu.add_command(label="Open Clean ME...", command=self._load_me,
                              accelerator="Ctrl+M")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="External Tools Status...",
                               command=self._show_tools_status)
        tools_menu.add_command(label="Run ME Analyzer on dump...",
                               command=self._run_mea_dump)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

        # Key bindings
        self.root.bind("<Control-d>", lambda e: self._load_dump())
        self.root.bind("<Control-b>", lambda e: self._load_vendor())
        self.root.bind("<Control-m>", lambda e: self._load_me())

        # Main layout: top = file inputs, middle = info panels, bottom = log + build
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Top: File inputs ──
        files_frame = ttk.LabelFrame(main, text="Input Files", padding=8)
        files_frame.pack(fill=tk.X, pady=(0, 8))

        # Dump
        f1 = ttk.Frame(files_frame)
        f1.pack(fill=tk.X, pady=2)
        ttk.Label(f1, text="Programmer Dump:", width=18, anchor="w").pack(side=tk.LEFT)
        self.dump_var = tk.StringVar(value="(none)")
        ttk.Label(f1, textvariable=self.dump_var, foreground="gray").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(f1, text="Browse...", command=self._load_dump, width=10).pack(side=tk.RIGHT)

        # Vendor BIOS
        f2 = ttk.Frame(files_frame)
        f2.pack(fill=tk.X, pady=2)
        ttk.Label(f2, text="Vendor BIOS:", width=18, anchor="w").pack(side=tk.LEFT)
        self.vendor_var = tk.StringVar(value="(none)")
        ttk.Label(f2, textvariable=self.vendor_var, foreground="gray").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(f2, text="Browse...", command=self._load_vendor, width=10).pack(side=tk.RIGHT)

        # Clean ME
        f3 = ttk.Frame(files_frame)
        f3.pack(fill=tk.X, pady=2)
        ttk.Label(f3, text="Clean ME Image:", width=18, anchor="w").pack(side=tk.LEFT)
        self.me_var = tk.StringVar(value="(optional)")
        ttk.Label(f3, textvariable=self.me_var, foreground="gray").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(f3, text="Browse...", command=self._load_me, width=10).pack(side=tk.RIGHT)

        # ── Middle: Info panels (two columns) ──
        panels = ttk.Frame(main)
        panels.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=1)

        # Left: Region map
        left_frame = ttk.LabelFrame(panels, text="Flash Layout", padding=6)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.region_tree = ttk.Treeview(left_frame, columns=("range", "size", "source"),
                                         show="headings", height=8)
        self.region_tree.heading("range", text="Address Range")
        self.region_tree.heading("size", text="Size")
        self.region_tree.heading("source", text="Source")
        self.region_tree.column("range", width=200)
        self.region_tree.column("size", width=80)
        self.region_tree.column("source", width=160)
        self.region_tree.pack(fill=tk.BOTH, expand=True)

        # Right: Details
        right_frame = ttk.LabelFrame(panels, text="Details", padding=6)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.details_text = scrolledtext.ScrolledText(
            right_frame, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED,
            bg="#1e1e1e", fg="#cccccc", insertbackground="white",
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # ── Bottom: Build button + log ──
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X)

        btn_frame = ttk.Frame(bottom)
        btn_frame.pack(fill=tk.X, pady=(0, 4))

        self.build_btn = ttk.Button(
            btn_frame, text="Build Flashable Image",
            command=self._build_image, state=tk.DISABLED,
        )
        self.build_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.status_var = tk.StringVar(value="Load a programmer dump to begin.")
        ttk.Label(btn_frame, textvariable=self.status_var,
                  foreground="gray").pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ── File Loading ─────────────────────────────────────────────────

    def _load_dump(self):
        path = filedialog.askopenfilename(
            title="Open Programmer Dump",
            filetypes=[("Binary files", "*.bin *.rom"), ("All files", "*.*")],
        )
        if not path:
            return

        data = Path(path).read_bytes()
        fname = os.path.basename(path)

        if not has_descriptor(data):
            messagebox.showerror(
                "Invalid Dump",
                f"{fname} does not contain a valid Intel Flash Descriptor.\n"
                "This file may not be a full SPI flash dump."
            )
            return

        try:
            desc = parse_descriptor(data)
        except ValueError as e:
            messagebox.showerror("Parse Error", str(e))
            return

        self.dump_data = data
        self.dump_path = path
        self.dump_descriptor = desc
        self.dump_var.set(f"{fname} ({len(data) / 1024 / 1024:.0f} MB)")

        # Parse ME region if present
        me = desc.me_region
        if me and me.enabled:
            try:
                me_data = data[me.base:me.limit + 1]
                self.dump_me_info = parse_me_region(me_data, me.base)
            except ValueError:
                self.dump_me_info = None

        self._update_region_map()
        self._update_details()
        self._update_build_button()
        self._log(f"Loaded dump: {fname}")
        self._log(desc.summary())
        if self.dump_me_info:
            self._log(self.dump_me_info.summary())

    def _load_vendor(self):
        path = filedialog.askopenfilename(
            title="Open Vendor BIOS Image",
            filetypes=[("BIOS files", "*.bin *.cap *.rom"), ("All files", "*.*")],
        )
        if not path:
            return

        data = Path(path).read_bytes()
        fname = os.path.basename(path)

        # Try auto-detection
        info = detect_vendor(data, fname)
        if info is None:
            messagebox.showwarning(
                "Unknown Format",
                f"Could not auto-detect vendor format for {fname}.\n"
                "Currently supported: HP"
            )
            return

        self.vendor_data = data
        self.vendor_path = path
        self.vendor_info = info
        label = f"{info.vendor} {info.version or fname}"
        if info.has_bios:
            label += f" (BIOS: {len(info.bios_data) / 1024 / 1024:.1f} MB)"
        self.vendor_var.set(label)

        self._update_region_map()
        self._update_details()
        self._update_build_button()
        self._log(f"Loaded vendor BIOS: {fname}")
        self._log(info.summary())

    def _load_me(self):
        path = filedialog.askopenfilename(
            title="Open Clean ME Image (full SPI dump with clean ME)",
            filetypes=[("Binary files", "*.bin *.rom"), ("All files", "*.*")],
        )
        if not path:
            return

        data = Path(path).read_bytes()
        fname = os.path.basename(path)

        # The ME source should be a full SPI dump with a valid descriptor
        if not has_descriptor(data):
            messagebox.showerror(
                "Invalid ME Source",
                f"{fname} does not have an Intel Flash Descriptor.\n"
                "The clean ME source should be a full SPI dump."
            )
            return

        try:
            desc = parse_descriptor(data)
        except ValueError as e:
            messagebox.showerror("Parse Error", str(e))
            return

        me = desc.me_region
        if not me or not me.enabled:
            messagebox.showerror(
                "No ME Region",
                f"{fname} does not contain an ME region."
            )
            return

        self.me_data = data
        self.me_path = path
        self.me_descriptor = desc

        # Parse ME info
        try:
            me_raw = data[me.base:me.limit + 1]
            self.me_info = parse_me_region(me_raw, me.base)
        except ValueError:
            self.me_info = None

        label = f"{fname} (ME: {me.size / 1024 / 1024:.1f} MB)"
        if self.me_info and self.me_info.version:
            label += f" v{self.me_info.version}"
        self.me_var.set(label)

        self._update_region_map()
        self._update_details()
        self._update_build_button()
        self._log(f"Loaded clean ME source: {fname}")
        if self.me_info:
            self._log(self.me_info.summary())

    # ── Build ────────────────────────────────────────────────────────

    def _build_image(self):
        if self.dump_data is None or self.dump_descriptor is None:
            return

        dump_name = os.path.basename(self.dump_path or "dump")
        builder = ImageBuilder(self.dump_data, dump_name)
        warnings = []

        # Apply vendor BIOS
        if self.vendor_info and self.vendor_info.has_bios:
            bios_region = self.dump_descriptor.bios_region
            if bios_region and bios_region.enabled:
                bios_data = self.vendor_info.bios_data
                if len(bios_data) == bios_region.size:
                    builder.set_bios(bios_data,
                                     f"{self.vendor_info.vendor} {self.vendor_info.version}")
                elif len(bios_data) < bios_region.size:
                    # Pad with 0xFF
                    padded = bios_data + b"\xff" * (bios_region.size - len(bios_data))
                    builder.set_bios(padded,
                                     f"{self.vendor_info.vendor} {self.vendor_info.version} (padded)")
                    warnings.append(
                        f"BIOS data was {len(bios_data)} bytes, "
                        f"padded to {bios_region.size} bytes with 0xFF"
                    )
                else:
                    # Truncate (unusual but handle it)
                    builder.set_bios(bios_data[:bios_region.size],
                                     f"{self.vendor_info.vendor} {self.vendor_info.version} (truncated)")
                    warnings.append(
                        f"BIOS data was {len(bios_data)} bytes, "
                        f"truncated to {bios_region.size} bytes"
                    )

        # Apply clean ME
        if self.me_data and self.me_descriptor:
            me_src = self.me_descriptor.me_region
            me_dst = self.dump_descriptor.me_region
            if me_src and me_dst and me_src.enabled and me_dst.enabled:
                me_raw = self.me_data[me_src.base:me_src.limit + 1]
                if len(me_raw) == me_dst.size:
                    me_name = os.path.basename(self.me_path or "clean ME")
                    builder.set_me(me_raw, me_name)
                else:
                    warnings.append(
                        f"ME size mismatch: source={len(me_raw)}, "
                        f"expected={me_dst.size}. Using dump's ME."
                    )

        # Build
        try:
            result = self.last_build = builder.build()
        except Exception as e:
            messagebox.showerror("Build Failed", str(e))
            return

        for w in warnings:
            result.warnings.append(w)

        self._log("\n" + "=" * 60)
        self._log("BUILD COMPLETE")
        self._log(result.summary())

        # Save dialog
        default_name = "flashable_output.bin"
        if self.vendor_info:
            default_name = f"{self.vendor_info.vendor}_{self.vendor_info.version or 'bios'}_flashable.bin"

        save_path = filedialog.asksaveasfilename(
            title="Save Flashable Image",
            defaultextension=".bin",
            initialfile=default_name,
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")],
        )

        if save_path:
            result.save(save_path)
            self._log(f"Saved to: {save_path}")
            self.status_var.set(f"Built and saved: {os.path.basename(save_path)}")
            messagebox.showinfo(
                "Build Complete",
                f"Flashable image saved!\n\n"
                f"File: {os.path.basename(save_path)}\n"
                f"Size: {result.size:,} bytes\n"
                f"MD5: {result.md5}\n\n"
                f"Warnings: {len(result.warnings)}"
            )
        else:
            self.status_var.set("Build complete (not saved)")

    # ── UI Updates ───────────────────────────────────────────────────

    def _update_region_map(self):
        """Refresh the region map treeview."""
        self.region_tree.delete(*self.region_tree.get_children())

        if not self.dump_descriptor:
            return

        for rtype, region in self.dump_descriptor.regions.items():
            if not region.enabled:
                continue

            addr = f"0x{region.base:08X} - 0x{region.limit:08X}"
            size = f"{region.size / 1024:.0f} KB"

            # Determine source
            source = os.path.basename(self.dump_path or "dump")
            if rtype == RegionType.BIOS and self.vendor_info and self.vendor_info.has_bios:
                source = f"{self.vendor_info.vendor} {self.vendor_info.version}"
            elif rtype == RegionType.ME and self.me_data:
                source = os.path.basename(self.me_path or "clean ME")

            self.region_tree.insert("", tk.END, values=(
                f"{region.name}: {addr}", size, source,
            ))

    def _update_details(self):
        """Refresh the details text panel."""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete("1.0", tk.END)

        if self.dump_descriptor:
            self.details_text.insert(tk.END, "=== DUMP ===\n")
            self.details_text.insert(tk.END, self.dump_descriptor.summary() + "\n\n")

        if self.dump_me_info:
            self.details_text.insert(tk.END, "=== DUMP ME ===\n")
            self.details_text.insert(tk.END, self.dump_me_info.summary() + "\n\n")

        if self.vendor_info:
            self.details_text.insert(tk.END, "=== VENDOR BIOS ===\n")
            self.details_text.insert(tk.END, self.vendor_info.summary() + "\n\n")

        if self.me_info:
            self.details_text.insert(tk.END, "=== CLEAN ME ===\n")
            self.details_text.insert(tk.END, self.me_info.summary() + "\n\n")

        self.details_text.config(state=tk.DISABLED)

    def _update_build_button(self):
        """Enable/disable build button based on loaded files."""
        can_build = (
            self.dump_data is not None
            and self.vendor_info is not None
            and self.vendor_info.has_bios
        )
        self.build_btn.config(state=tk.NORMAL if can_build else tk.DISABLED)

        if can_build:
            self.status_var.set("Ready to build. Clean ME is optional.")
        elif self.dump_data:
            self.status_var.set("Load a vendor BIOS image to continue.")
        else:
            self.status_var.set("Load a programmer dump to begin.")

    def _log(self, message: str):
        """Append a message to the details/log panel."""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.insert(tk.END, message + "\n")
        self.details_text.see(tk.END)
        self.details_text.config(state=tk.DISABLED)

    # ── External Tools ───────────────────────────────────────────────

    def _check_tools(self):
        """Check for available external tools on startup."""
        self.tools.discover_all()

    def _show_tools_status(self):
        report = self.tools.status_report()
        win = tk.Toplevel(self.root)
        win.title("External Tools Status")
        win.geometry("600x400")
        text = scrolledtext.ScrolledText(win, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, report)
        text.config(state=tk.DISABLED)

    def _run_mea_dump(self):
        if not self.dump_path:
            messagebox.showinfo("No dump", "Load a dump first.")
            return
        output = self.tools.run_meanalyzer(self.dump_path)
        if output:
            self._log("\n=== ME Analyzer Output ===")
            self._log(output)
        else:
            messagebox.showwarning(
                "ME Analyzer",
                "ME Analyzer not found.\n"
                "Download from: https://github.com/platomav/MEAnalyzer"
            )

    def _show_about(self):
        messagebox.showinfo(
            "About biosforge",
            "biosforge v0.2.0-alpha\n\n"
            "Open source UEFI/BIOS firmware reconstruction toolkit.\n\n"
            "Integrates: UEFITool, ME Analyzer, me_cleaner,\n"
            "ifdtool, flashrom, BIOSUtilities, MCExtractor\n\n"
            "License: BSD-2-Clause\n"
            "https://github.com/lucasgonzalezz/biosforge"
        )


def main():
    app = BiosForgeApp()
    app.run()


if __name__ == "__main__":
    main()
