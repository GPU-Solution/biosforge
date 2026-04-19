"""Intel/AMD CPUID → Platform identification database.

Maps processor CPUID signatures found in microcode updates to their
platform family, codename, socket, chipset generation, and expected
ME/CSME version. This allows biosforge to identify the exact platform
from a raw SPI flash dump just by reading the microcode headers.

Intel CPUID format: Family[7:0] + Model[7:0] + Stepping[3:0]
  Extended: Family = ExtFamily[7:0] + Family[3:0]
            Model  = ExtModel[3:0] << 4 | Model[3:0]

Sources: Intel SDM, coreboot devicetree, MCExtractor database,
         WikiChip, kernel.org microcode changelogs.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformDef:
    """Platform definition linked to a CPUID signature."""
    cpuid: int              # Full CPUID signature (family + model + stepping mask)
    codename: str           # Intel codename (e.g., "Kaby Lake")
    family: str             # Marketing family (e.g., "6th/7th Gen Core")
    segment: str            # "mobile", "desktop", "server", "embedded"
    socket: str             # Socket (e.g., "LGA1151", "BGA1356")
    pch: str                # Expected PCH/chipset (e.g., "100/200 Series")
    me_generation: str      # Expected ME/CSME generation (e.g., "CSME 11.x")
    launch_year: int        # Launch year
    notes: str = ""         # Additional notes


# CPUID mask: we match on Family + Model, ignoring stepping (lowest nibble).
# Some entries include stepping for disambiguation.
#
# Format: cpuid_signature → PlatformDef
# The signature is CPUID EAX value with stepping masked to 0 for broad match.

INTEL_CPUID_DB: dict[int, PlatformDef] = {

    # ── Sandy Bridge (2011) ──────────────────────────────────────────
    0x206A0: PlatformDef(
        cpuid=0x206A0, codename="Sandy Bridge",
        family="2nd Gen Core", segment="desktop/mobile",
        socket="LGA1155 / BGA1023", pch="6 Series (P67/H67/Z68/HM65)",
        me_generation="ME 7.x", launch_year=2011,
    ),
    0x206D0: PlatformDef(
        cpuid=0x206D0, codename="Sandy Bridge-E/EN/EP",
        family="Core i7 Extreme / Xeon E5", segment="server/HEDT",
        socket="LGA2011", pch="X79 / C600",
        me_generation="ME 7.x", launch_year=2011,
    ),

    # ── Ivy Bridge (2012) ────────────────────────────────────────────
    0x306A0: PlatformDef(
        cpuid=0x306A0, codename="Ivy Bridge",
        family="3rd Gen Core", segment="desktop/mobile",
        socket="LGA1155 / BGA1023", pch="7 Series (Z77/H77/HM76)",
        me_generation="ME 8.x", launch_year=2012,
    ),
    0x306E0: PlatformDef(
        cpuid=0x306E0, codename="Ivy Bridge-E/EN/EP",
        family="Core i7 Extreme / Xeon E5 v2", segment="server/HEDT",
        socket="LGA2011", pch="X79 / C600",
        me_generation="ME 8.x", launch_year=2013,
    ),

    # ── Haswell (2013) ───────────────────────────────────────────────
    0x306C0: PlatformDef(
        cpuid=0x306C0, codename="Haswell",
        family="4th Gen Core", segment="desktop/mobile",
        socket="LGA1150 / BGA1364", pch="8 Series (Z87/H87/HM86)",
        me_generation="ME 9.x", launch_year=2013,
    ),
    0x40650: PlatformDef(
        cpuid=0x40650, codename="Haswell ULT",
        family="4th Gen Core (U/Y)", segment="mobile/ultrabook",
        socket="BGA1168", pch="8 Series LP (Lynx Point LP)",
        me_generation="ME 9.x", launch_year=2013,
    ),
    0x40660: PlatformDef(
        cpuid=0x40660, codename="Haswell Crystal Well",
        family="4th Gen Core (Iris)", segment="mobile",
        socket="BGA1364", pch="8 Series",
        me_generation="ME 9.x", launch_year=2013,
    ),
    0x306F0: PlatformDef(
        cpuid=0x306F0, codename="Haswell-E/EN/EP",
        family="Core i7 Extreme / Xeon E5 v3", segment="server/HEDT",
        socket="LGA2011-v3", pch="X99 / C610",
        me_generation="ME 9.x / 10.x", launch_year=2014,
    ),

    # ── Broadwell (2014-2015) ────────────────────────────────────────
    0x306D0: PlatformDef(
        cpuid=0x306D0, codename="Broadwell",
        family="5th Gen Core (U/Y)", segment="mobile/ultrabook",
        socket="BGA1168 / BGA1234", pch="9 Series LP (Wildcat Point LP)",
        me_generation="ME 10.x", launch_year=2014,
    ),
    0x40670: PlatformDef(
        cpuid=0x40670, codename="Broadwell Crystal Well",
        family="5th Gen Core (Iris Pro)", segment="desktop/mobile",
        socket="LGA1150 / BGA1364", pch="9 Series",
        me_generation="ME 10.x", launch_year=2015,
    ),
    0x406F0: PlatformDef(
        cpuid=0x406F0, codename="Broadwell-E/EN/EP",
        family="Core i7 Extreme / Xeon E5 v4", segment="server/HEDT",
        socket="LGA2011-v3", pch="X99 / C610",
        me_generation="ME 10.x", launch_year=2016,
    ),
    0x50660: PlatformDef(
        cpuid=0x50660, codename="Broadwell-DE",
        family="Xeon D-1500", segment="server/embedded",
        socket="BGA1667", pch="Integrated",
        me_generation="SPS 3.x", launch_year=2015,
    ),

    # ── Skylake (2015) ───────────────────────────────────────────────
    0x506E0: PlatformDef(
        cpuid=0x506E0, codename="Skylake",
        family="6th Gen Core", segment="desktop/mobile",
        socket="LGA1151 / BGA1356 / BGA1515", pch="100 Series (Z170/H170/HM170)",
        me_generation="CSME 11.0", launch_year=2015,
    ),
    0x50650: PlatformDef(
        cpuid=0x50650, codename="Skylake-X/W",
        family="Core X / Xeon W", segment="HEDT/workstation",
        socket="LGA2066", pch="X299 / C620",
        me_generation="CSME 11.x", launch_year=2017,
    ),
    0x50670: PlatformDef(
        cpuid=0x50670, codename="Skylake-SP",
        family="Xeon Scalable (1st Gen)", segment="server",
        socket="LGA3647", pch="C620",
        me_generation="SPS 4.x", launch_year=2017,
    ),

    # ── Kaby Lake (2016-2017) ────────────────────────────────────────
    0x806E0: PlatformDef(
        cpuid=0x806E0, codename="Kaby Lake / Kaby Lake-R",
        family="7th/8th Gen Core (U/Y)", segment="mobile",
        socket="BGA1356 / BGA1515", pch="100/200 Series (HM175/CM238)",
        me_generation="CSME 11.x", launch_year=2016,
        notes="Kaby Lake-R (8th Gen) shares same CPUID",
    ),
    0x906E0: PlatformDef(
        cpuid=0x906E0, codename="Kaby Lake",
        family="7th Gen Core (S/H)", segment="desktop",
        socket="LGA1151", pch="200 Series (Z270/H270/B250)",
        me_generation="CSME 11.x", launch_year=2017,
    ),

    # ── Coffee Lake (2017-2019) ──────────────────────────────────────
    0x906EA: PlatformDef(
        cpuid=0x906EA, codename="Coffee Lake",
        family="8th Gen Core (S/H)", segment="desktop",
        socket="LGA1151", pch="300 Series (Z370/H370/B360)",
        me_generation="CSME 12.x", launch_year=2017,
    ),
    0x906EB: PlatformDef(
        cpuid=0x906EB, codename="Coffee Lake",
        family="8th Gen Core", segment="desktop",
        socket="LGA1151", pch="300 Series",
        me_generation="CSME 12.x", launch_year=2018,
    ),
    0x906EC: PlatformDef(
        cpuid=0x906EC, codename="Coffee Lake Refresh",
        family="9th Gen Core", segment="desktop",
        socket="LGA1151", pch="300 Series (Z390/B365)",
        me_generation="CSME 12.x", launch_year=2018,
    ),
    0x906ED: PlatformDef(
        cpuid=0x906ED, codename="Coffee Lake Refresh",
        family="9th Gen Core", segment="desktop",
        socket="LGA1151", pch="300 Series (Z390)",
        me_generation="CSME 12.x", launch_year=2019,
    ),
    0x806EA: PlatformDef(
        cpuid=0x806EA, codename="Coffee Lake-U",
        family="8th Gen Core (U)", segment="mobile",
        socket="BGA1528", pch="300 Series LP (Cannon Point LP)",
        me_generation="CSME 12.x", launch_year=2018,
        notes="Whiskey Lake shares this CPUID on some steppings",
    ),
    0x806EB: PlatformDef(
        cpuid=0x806EB, codename="Whiskey Lake",
        family="8th Gen Core (U)", segment="mobile",
        socket="BGA1528", pch="300 Series LP",
        me_generation="CSME 12.x", launch_year=2018,
    ),

    # ── Cannon Lake (2018, limited) ──────────────────────────────────
    0x60660: PlatformDef(
        cpuid=0x60660, codename="Cannon Lake",
        family="8th Gen Core (limited)", segment="mobile",
        socket="BGA1440", pch="Cannon Point",
        me_generation="CSME 12.x", launch_year=2018,
        notes="Very limited release (Core i3-8121U)",
    ),

    # ── Comet Lake (2019-2020) ───────────────────────────────────────
    0x806EC: PlatformDef(
        cpuid=0x806EC, codename="Comet Lake-U",
        family="10th Gen Core (U)", segment="mobile",
        socket="BGA1528", pch="400 Series LP (Comet Point LP)",
        me_generation="CSME 14.x", launch_year=2019,
    ),
    0xA0650: PlatformDef(
        cpuid=0xA0650, codename="Comet Lake",
        family="10th Gen Core (S)", segment="desktop",
        socket="LGA1200", pch="400 Series (Z490/H470/B460)",
        me_generation="CSME 14.x", launch_year=2020,
    ),
    0xA0660: PlatformDef(
        cpuid=0xA0660, codename="Comet Lake",
        family="10th Gen Core (S)", segment="desktop",
        socket="LGA1200", pch="400 Series",
        me_generation="CSME 14.x", launch_year=2020,
    ),

    # ── Ice Lake (2019) ──────────────────────────────────────────────
    0x706E0: PlatformDef(
        cpuid=0x706E0, codename="Ice Lake",
        family="10th Gen Core (U/Y)", segment="mobile",
        socket="BGA1526", pch="Ice Point LP",
        me_generation="CSME 13.x", launch_year=2019,
        notes="10nm process, first Ice Lake mobile",
    ),
    0x606A0: PlatformDef(
        cpuid=0x606A0, codename="Ice Lake-SP",
        family="Xeon Scalable (3rd Gen)", segment="server",
        socket="LGA4189", pch="C620A",
        me_generation="SPS 5.x", launch_year=2021,
    ),

    # ── Tiger Lake (2020) ────────────────────────────────────────────
    0x806C0: PlatformDef(
        cpuid=0x806C0, codename="Tiger Lake",
        family="11th Gen Core (U/Y)", segment="mobile",
        socket="BGA1449 / BGA1526", pch="Tiger Point LP",
        me_generation="CSME 15.x", launch_year=2020,
    ),
    0x806D0: PlatformDef(
        cpuid=0x806D0, codename="Tiger Lake-H",
        family="11th Gen Core (H)", segment="mobile",
        socket="BGA1787", pch="500 Series (HM570)",
        me_generation="CSME 15.x", launch_year=2021,
    ),

    # ── Rocket Lake (2021) ───────────────────────────────────────────
    0xA0670: PlatformDef(
        cpuid=0xA0670, codename="Rocket Lake",
        family="11th Gen Core (S)", segment="desktop",
        socket="LGA1200", pch="500 Series (Z590/H570/B560)",
        me_generation="CSME 15.x", launch_year=2021,
    ),

    # ── Alder Lake (2021-2022) ───────────────────────────────────────
    0x90670: PlatformDef(
        cpuid=0x90670, codename="Alder Lake",
        family="12th Gen Core", segment="desktop",
        socket="LGA1700", pch="600 Series (Z690/H670/B660)",
        me_generation="CSME 16.x", launch_year=2021,
        notes="First hybrid P-core + E-core",
    ),
    0x906A0: PlatformDef(
        cpuid=0x906A0, codename="Alder Lake-P/U",
        family="12th Gen Core (P/U)", segment="mobile",
        socket="BGA1744 / BGA1781", pch="Alder Point PCH",
        me_generation="CSME 16.x", launch_year=2022,
    ),
    0x906A4: PlatformDef(
        cpuid=0x906A4, codename="Alder Lake-P",
        family="12th Gen Core (P)", segment="mobile",
        socket="BGA1744", pch="Alder Point PCH",
        me_generation="CSME 16.x", launch_year=2022,
    ),
    0xB06A0: PlatformDef(
        cpuid=0xB06A0, codename="Alder Lake-N",
        family="Intel N-series (N95/N100/N200/N305)", segment="mobile/embedded",
        socket="BGA1264", pch="Integrated",
        me_generation="CSME 16.x", launch_year=2023,
        notes="E-cores only, integrated PCH",
    ),

    # ── Raptor Lake (2022-2023) ──────────────────────────────────────
    0xB0670: PlatformDef(
        cpuid=0xB0670, codename="Raptor Lake",
        family="13th Gen Core", segment="desktop",
        socket="LGA1700", pch="700 Series (Z790/H770/B760)",
        me_generation="CSME 16.x", launch_year=2022,
    ),
    0xB06A2: PlatformDef(
        cpuid=0xB06A2, codename="Raptor Lake-P",
        family="13th Gen Core (P/U)", segment="mobile",
        socket="BGA1744", pch="Raptor Point PCH",
        me_generation="CSME 16.x", launch_year=2023,
    ),
    0xB06F0: PlatformDef(
        cpuid=0xB06F0, codename="Raptor Lake Refresh",
        family="14th Gen Core", segment="desktop",
        socket="LGA1700", pch="700 Series",
        me_generation="CSME 16.x", launch_year=2023,
        notes="Raptor Lake Refresh = 14th Gen desktop",
    ),

    # ── Meteor Lake (2023) ───────────────────────────────────────────
    0xA06A0: PlatformDef(
        cpuid=0xA06A0, codename="Meteor Lake",
        family="Intel Core Ultra (Series 1)", segment="mobile",
        socket="BGA2551", pch="Integrated (chiplet)",
        me_generation="CSME 18.x", launch_year=2023,
        notes="First chiplet-based Intel mobile",
    ),

    # ── Arrow Lake (2024) ────────────────────────────────────────────
    0xC0660: PlatformDef(
        cpuid=0xC0660, codename="Arrow Lake",
        family="Intel Core Ultra 200S", segment="desktop",
        socket="LGA1851", pch="800 Series (Z890/H870/B860)",
        me_generation="CSME 18.x", launch_year=2024,
    ),
    0xC06A0: PlatformDef(
        cpuid=0xC06A0, codename="Arrow Lake-H",
        family="Intel Core Ultra 200H", segment="mobile",
        socket="BGA", pch="Integrated",
        me_generation="CSME 18.x", launch_year=2024,
    ),

    # ── Atom / Low-Power ─────────────────────────────────────────────
    0x30670: PlatformDef(
        cpuid=0x30670, codename="Bay Trail",
        family="Atom Z3xxx / Celeron N/J", segment="mobile/embedded",
        socket="BGA1170", pch="Integrated",
        me_generation="TXE 1.x", launch_year=2013,
    ),
    0x406C0: PlatformDef(
        cpuid=0x406C0, codename="Cherry Trail",
        family="Atom x5/x7", segment="mobile/tablet",
        socket="BGA1380", pch="Integrated",
        me_generation="TXE 2.x", launch_year=2015,
    ),
    0x506C0: PlatformDef(
        cpuid=0x506C0, codename="Apollo Lake",
        family="Pentium/Celeron N/J (Goldmont)", segment="mobile/embedded",
        socket="BGA1296", pch="Integrated",
        me_generation="TXE 3.x", launch_year=2016,
    ),
    0x706A0: PlatformDef(
        cpuid=0x706A0, codename="Gemini Lake",
        family="Pentium/Celeron N/J (Goldmont+)", segment="mobile/embedded",
        socket="BGA1090", pch="Integrated",
        me_generation="TXE 4.x", launch_year=2017,
    ),
    0x506F0: PlatformDef(
        cpuid=0x506F0, codename="Denverton",
        family="Atom C3xxx", segment="server/embedded",
        socket="BGA1310", pch="Integrated",
        me_generation="SPS 4.x", launch_year=2017,
    ),
    0x90660: PlatformDef(
        cpuid=0x90660, codename="Elkhart Lake",
        family="Pentium/Celeron J/N (Tremont)", segment="embedded",
        socket="BGA1493", pch="Integrated",
        me_generation="CSME 14.x", launch_year=2020,
    ),
    0x90670 | 0x1: PlatformDef(  # disambiguation from Alder Lake desktop
        cpuid=0x90671, codename="Jasper Lake",
        family="Pentium/Celeron N (Tremont)", segment="mobile/embedded",
        socket="BGA1338", pch="Integrated",
        me_generation="CSME 15.x", launch_year=2021,
        notes="CPUID may overlap with Alder Lake steppings",
    ),
}


# ── AMD CPUIDs (basic coverage) ──────────────────────────────────────

AMD_CPUID_DB: dict[int, PlatformDef] = {
    0x800F00: PlatformDef(
        cpuid=0x800F00, codename="Zen (Summit Ridge)",
        family="Ryzen 1000", segment="desktop",
        socket="AM4", pch="X370/B350/A320",
        me_generation="N/A (AMD PSP)", launch_year=2017,
    ),
    0x800F10: PlatformDef(
        cpuid=0x800F10, codename="Zen (Whitehaven)",
        family="Threadripper 1000", segment="HEDT",
        socket="TR4", pch="X399",
        me_generation="N/A (AMD PSP)", launch_year=2017,
    ),
    0x800F80: PlatformDef(
        cpuid=0x800F80, codename="Zen (Raven Ridge)",
        family="Ryzen 2000 APU", segment="desktop/mobile",
        socket="AM4 / FP5", pch="Integrated",
        me_generation="N/A (AMD PSP)", launch_year=2018,
    ),
    0x800F82: PlatformDef(
        cpuid=0x800F82, codename="Zen+ (Picasso)",
        family="Ryzen 3000 APU", segment="mobile",
        socket="FP5", pch="Integrated",
        me_generation="N/A (AMD PSP)", launch_year=2019,
    ),
    0x810F00: PlatformDef(
        cpuid=0x810F00, codename="Zen (Dhyana)",
        family="Hygon C86", segment="server",
        socket="LGA4094", pch="N/A",
        me_generation="N/A", launch_year=2019,
    ),
    0x810F10: PlatformDef(
        cpuid=0x810F10, codename="Zen (Naples)",
        family="EPYC 7001", segment="server",
        socket="SP3", pch="N/A",
        me_generation="N/A (AMD PSP)", launch_year=2017,
    ),
    0x830F00: PlatformDef(
        cpuid=0x830F00, codename="Zen 2 (Castle Peak)",
        family="Threadripper 3000", segment="HEDT",
        socket="TRX40", pch="TRX40",
        me_generation="N/A (AMD PSP)", launch_year=2019,
    ),
    0x830F10: PlatformDef(
        cpuid=0x830F10, codename="Zen 2 (Rome)",
        family="EPYC 7002", segment="server",
        socket="SP3", pch="N/A",
        me_generation="N/A (AMD PSP)", launch_year=2019,
    ),
    0x860F00: PlatformDef(
        cpuid=0x860F00, codename="Zen 2 (Renoir)",
        family="Ryzen 4000 APU", segment="mobile",
        socket="FP6", pch="Integrated",
        me_generation="N/A (AMD PSP)", launch_year=2020,
    ),
    0x860F01: PlatformDef(
        cpuid=0x860F01, codename="Zen 2 (Lucienne)",
        family="Ryzen 5000 APU (Zen2)", segment="mobile",
        socket="FP6", pch="Integrated",
        me_generation="N/A (AMD PSP)", launch_year=2021,
    ),
    0xA20F00: PlatformDef(
        cpuid=0xA20F00, codename="Zen 3 (Vermeer)",
        family="Ryzen 5000", segment="desktop",
        socket="AM4", pch="X570/B550/A520",
        me_generation="N/A (AMD PSP)", launch_year=2020,
    ),
    0xA40F00: PlatformDef(
        cpuid=0xA40F00, codename="Zen 3 (Cezanne)",
        family="Ryzen 5000 APU", segment="mobile/desktop",
        socket="FP6 / AM4", pch="Integrated / X570",
        me_generation="N/A (AMD PSP)", launch_year=2021,
    ),
    0xA60F00: PlatformDef(
        cpuid=0xA60F00, codename="Zen 3+ (Rembrandt)",
        family="Ryzen 6000", segment="mobile",
        socket="FP7", pch="Integrated",
        me_generation="N/A (AMD PSP)", launch_year=2022,
    ),
    0xA70F00: PlatformDef(
        cpuid=0xA70F00, codename="Zen 4 (Phoenix)",
        family="Ryzen 7040", segment="mobile",
        socket="FP7r2 / FP8", pch="Integrated",
        me_generation="N/A (AMD PSP)", launch_year=2023,
    ),
    0x660F00: PlatformDef(
        cpuid=0x660F00, codename="Zen 4 (Raphael)",
        family="Ryzen 7000", segment="desktop",
        socket="AM5", pch="X670E/X670/B650E/B650",
        me_generation="N/A (AMD PSP)", launch_year=2022,
    ),
    0x660F10: PlatformDef(
        cpuid=0x660F10, codename="Zen 4 (Genoa)",
        family="EPYC 9004", segment="server",
        socket="SP5", pch="N/A",
        me_generation="N/A (AMD PSP)", launch_year=2022,
    ),
}


def lookup_cpuid(cpuid: int) -> Optional[PlatformDef]:
    """Look up a CPUID in the database.

    Tries exact match first, then masks off stepping (lowest nibble)
    for a broader match.

    Args:
        cpuid: Raw CPUID value (from microcode header or CPUID instruction).

    Returns:
        PlatformDef if found, None otherwise.
    """
    # Exact match
    if cpuid in INTEL_CPUID_DB:
        return INTEL_CPUID_DB[cpuid]
    if cpuid in AMD_CPUID_DB:
        return AMD_CPUID_DB[cpuid]

    # Mask stepping (lowest nibble) for Intel
    masked = cpuid & 0xFFFF0
    if masked in INTEL_CPUID_DB:
        return INTEL_CPUID_DB[masked]

    # Mask stepping for AMD (lowest byte for broader match)
    masked_amd = cpuid & 0xFFFF00
    if masked_amd in AMD_CPUID_DB:
        return AMD_CPUID_DB[masked_amd]

    # Try just upper nibble masking
    masked2 = cpuid & 0xFFFFF0
    if masked2 in INTEL_CPUID_DB:
        return INTEL_CPUID_DB[masked2]

    return None


def format_cpuid(cpuid: int) -> str:
    """Format a CPUID value for display.

    Returns string like '06-8E-0A' (family-model-stepping).
    """
    # Intel format: ExtFamily_ExtModel_Family_Model_Stepping
    stepping = cpuid & 0xF
    model = (cpuid >> 4) & 0xF
    family = (cpuid >> 8) & 0xF
    ext_model = (cpuid >> 16) & 0xF
    ext_family = (cpuid >> 20) & 0xFF

    display_family = ext_family + family
    display_model = (ext_model << 4) | model

    return f"{display_family:02X}-{display_model:02X}-{stepping:02X}"


def get_all_platforms() -> list[PlatformDef]:
    """Get all platforms sorted by launch year."""
    all_platforms = list(INTEL_CPUID_DB.values()) + list(AMD_CPUID_DB.values())
    return sorted(all_platforms, key=lambda p: p.launch_year)
