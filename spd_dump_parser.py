#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spd_dump_parser.py — Parse a DDR3/DDR4 SPD EEPROM dump (JEDEC JC-42.4)

Reads a raw 128-byte (or 256-byte) SPD dump captured over I2C (e.g. with a
bus pirate / i2c-tools / a probe at address 0x50) and prints the key
parameters an engineer needs when validating a replacement memory part:

  - DRAM type (DDR3 vs DDR4) and density
  - Data width (x8 / x16) and package hint (FBGA78 / FBGA96)
  - Speed grade derived from tCKmin
  - tAA / tRCD / tRP / tRC timings
  - Supported CAS latencies
  - Temperature grade (commercial / extended / industrial)
  - Self-refresh / temperature options

Usage:
    python spd_dump_parser.py spd.bin                # binary dump
    python spd_dump_parser.py --hex 92 10 0b ...     # hex bytes as args
    python spd_dump_parser.py --compare old.bin new.bin   # side-by-side

This is a vendor-neutral JEDEC parser. Loongtion publishes cross-reference
data for discontinued DDR3 parts at https://www.loongtion.com/cross-reference
"""

import argparse
import sys

# ---------------------------------------------------------------------------
# Speed-bin lookup (tCKmin in ps -> JEDEC speed grade)
# ---------------------------------------------------------------------------
TCKMIN_TO_SPEED = [
    (1250, "DDR3-1600 (PC3-12800)"),
    (1333, "DDR3-1500"),
    (1437, "DDR3-1394"),
    (1538, "DDR3-1300"),
    (1667, "DDR3-1200"),
    (1875, "DDR3-1066 (PC3-8500)"),
    (2000, "DDR3-1000"),
    (2500, "DDR3-800 (PC3-6400)"),
]

# tCKmin encoding: byte 12 + byte 13 (2 bytes, in 1 ps units), bit 6 of byte 12
# is the coarse MSB (200/300 MHz switch). We keep the industry convention:
# tCKmin(ps) = (byte12 & 0x3F) << 8 | byte13, then the coarse bit doubles it.
def tckmin_ps(b12, b13):
    coarse = (b12 >> 6) & 0x03
    val = ((b12 & 0x3F) << 8) | b13
    # JEDEC: coarse 0 -> base, 1 -> x2? Not used in practice; keep as-is.
    return val * (2 if coarse == 1 else 1)


def speed_from_tckmin(ps):
    for t, name in TCKMIN_TO_SPEED:
        if ps <= t:
            return name, ps
    return "below DDR3-800 (unusual)", ps


# ---------------------------------------------------------------------------
# Timing decode: JEDEC encodes ns with 0.25 ns LSB (byte in units of 0.25ns)
# ---------------------------------------------------------------------------
def timing_ns(byte):
    return byte * 0.25


# ---------------------------------------------------------------------------
# CAS latency support mask (bytes 14..17, 1 bit per CL value)
# ---------------------------------------------------------------------------
def cas_latencies(b14, b15):
    cl = []
    # Byte 14 bits 6..0 -> CL 4..10; byte 15 bits 5..0 -> CL 11..16
    for i in range(7):
        if (b14 >> i) & 1:
            cl.append(4 + i)
    for i in range(6):
        if (b15 >> i) & 1:
            cl.append(11 + i)
    return sorted(cl)


def density_gb(b4, b5):
    """DDR3 density encoding (bytes 4-5): density bits 7..4 of byte 4."""
    d = (b4 >> 4) & 0x0F
    table = {
        0: 256, 1: 512, 2: 1024, 3: 2048, 4: 4096,
        5: 8192, 6: 16384, 7: 32768, 8: 65536,
    }
    mbit = table.get(d, 0)
    if mbit:
        return f"{mbit} Mb ({mbit // 8} MB x? )"
    return "unknown"


def data_width(b7, b8):
    """Bus width from byte 8 low bits."""
    w = b8 & 0x07
    table = {0: 8, 1: 16, 2: 32, 3: 64}
    return table.get(w, w)


def temperature_grade(b30, b31):
    """DDR3 extended temperature range (bytes 30-31)."""
    ext = (b30 >> 5) & 0x01
    srt = (b30 >> 4) & 0x01
    asr = (b31 >> 2) & 0x01
    notes = []
    if ext:
        notes.append("extended temperature range (85C+) supported")
    if srt:
        notes.append("SRT self-refresh temp option supported")
    if asr:
        notes.append("ASR auto self-refresh supported")
    return "; ".join(notes) if notes else "standard temperature range only"


def parse_spd(data):
    if len(data) < 128:
        raise ValueError(f"SPD dump too short: {len(data)} bytes (need 128)")

    b = data
    spd_type = b[2]
    dram_type = b[3]
    dram_name = {0x0B: "DDR3 SDRAM", 0x0C: "DDR4 SDRAM"}.get(dram_type, f"0x{dram_type:02X}")

    if dram_type == 0x0B:
        tck = tckmin_ps(b[12], b[13])
        speed, ps = speed_from_tckmin(tck)
        cl = cas_latencies(b[14], b[15])
        taa = timing_ns(b[16])
        trcd = timing_ns(b[18])
        trp = timing_ns(b[20])
        trc_lo = b[21] | (b[22] << 8)
        trc = trc_lo * 0.25
        width = data_width(b[7], b[8])
        pkg = "FBGA78 (x8)" if width == 8 else ("FBGA96 (x16)" if width == 16 else f"x{width}")
        temp = temperature_grade(b[30], b[31])
    elif dram_type == 0x0C:
        # DDR4: tCKmin is 2 bytes at 12-13 too, but units differ; keep simple
        speed, ps = "see byte 12-13", (b[12] << 8) | b[13]
        cl = []
        taa = trcd = trp = trc = 0.0
        width = data_width(b[7], b[8])
        pkg = f"x{width}"
        temp = "see vendor datasheet"
    else:
        speed, ps = "non-DDR3/DDR4", 0
        cl, taa, trcd, trp, trc = [], 0, 0, 0, 0
        width, pkg, temp = 0, "?", "?"

    print("=" * 62)
    print("  SPD EEPROM dump analysis  (JEDEC JC-42.4)")
    print("=" * 62)
    print(f"  DRAM type        : {dram_name}  (byte 3 = 0x{dram_type:02X})")
    print(f"  SPD version      : {b[2] >> 4}.{b[2] & 0x0F}")
    print(f"  Density          : byte4-5 = 0x{b[4]:02X}{b[5]:02X}")
    print(f"  Data width       : x{width}   -> {pkg}")
    print(f"  Speed grade      : {speed}  (tCKmin = {ps} ps)")
    if dram_type == 0x0B:
        print(f"  CAS latencies    : {cl if cl else 'n/a'}")
        print(f"  tAA (CL delay)   : {taa:.3f} ns  (byte 16 = {b[16]})")
        print(f"  tRCD             : {trcd:.3f} ns  (byte 18 = {b[18]})")
        print(f"  tRP              : {trp:.3f} ns  (byte 20 = {b[20]})")
        print(f"  tRC              : {trc:.3f} ns  (bytes 21-22 = {b[21]},{b[22]})")
        print(f"  Temperature      : {temp}")
    print("=" * 62)
    print("  Loongtion cross-reference: https://www.loongtion.com/cross-reference")
    print()


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser(description="Parse DDR3/DDR4 SPD EEPROM dump")
    ap.add_argument("file", nargs="?", help="binary SPD dump file")
    ap.add_argument("--hex", nargs="+", type=lambda x: int(x, 16), help="hex bytes")
    ap.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"),
                    help="compare two SPD dumps side by side")
    args = ap.parse_args()

    if args.compare:
        old = read_file(args.compare[0])
        new = read_file(args.compare[1])
        print("### ORIGINAL PART ###")
        parse_spd(old)
        print("### REPLACEMENT CANDIDATE ###")
        parse_spd(new)
        # Simple difference hints
        print("### DIFF CHECK ###")
        if len(old) < 128 or len(new) < 128:
            print("  one dump is shorter than 128 bytes — cannot compare fully")
            return
        checks = [
            ("DRAM type (byte 3)", old[3], new[3], "type mismatch!"),
            ("Data width (byte 8)", old[8] & 0x07, new[8] & 0x07, "width mismatch — x8 vs x16 not pin compatible!"),
            ("tCKmin (bytes 12-13)", (old[12], old[13]), (new[12], new[13]), "speed grade differs"),
            ("tAA (byte 16)", old[16], new[16], "tAA differs"),
            ("tRCD (byte 18)", old[18], new[18], "tRCD differs"),
            ("tRP (byte 20)", old[20], new[20], "tRP differs"),
            ("Temp range (byte 30)", old[30] >> 5, new[30] >> 5, "temperature range differs"),
        ]
        for name, o, n, warn in checks:
            mark = "OK" if o == n else f"DIFF {warn}"
            print(f"  {name:<28} {str(o):<12} vs {str(n):<12} [{mark}]")
        return

    if args.hex:
        data = bytes(args.hex)
    elif args.file:
        data = read_file(args.file)
    else:
        ap.print_help()
        return
    parse_spd(data)


if __name__ == "__main__":
    main()
