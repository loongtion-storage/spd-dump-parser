# SPD Dump Parser

Parse a raw **DDR3 / DDR4 SPD EEPROM dump** (JEDEC JC-42.4) captured over I2C
and print the parameters an engineer actually checks when validating a
replacement memory part after an EOL (end-of-life) notice.

Built by the engineers at [Loongtion (龙瑆)](https://www.loongtion.com) —
industrial-grade memory and storage manufacturer (DDR3 / DDR4 / DDR5,
eMMC, NVMe BGA, M.2 SSD, SATA DOM). We publish cross-reference data for
discontinued memory parts at <https://www.loongtion.com/cross-reference>.

---

## Why this exists

When a memory part goes EOL (Micron MT41K128M16JT, ISSI IS43TR16256BL,
Winbond W632GU6KB — the list keeps growing), the "pin-to-pin compatible"
replacement still has to be **verified at the SPD level**, not just by
marking or part number:

- **Package / width** — DDR3 ×16 uses FBGA96, ×8 uses FBGA78. They are not
  interchangeable. A width mismatch means *not* pin-compatible.
- **Speed grade** — tCKmin encodes the speed bin. "Equivalent" on the
  datasheet is not the same as identical in SPD bytes.
- **Timings** — tAA / tRCD / tRP / tRC are what the memory controller's
  timing budget was tuned against. Looser timings on the replacement show up
  as intermittent faults in the field, not at the bench.
- **Temperature range** — commercial (0..+70°C) vs wide-temp (−40..+85°C)
  vs extreme (−55..+105°C) matters when the enclosure is unheated.

This tool gives you a fast, objective dump-to-dump comparison.

## Install / run

Pure Python 3, no dependencies:

```bash
# From a binary dump captured from an I2C probe at 0x50:
python spd_dump_parser.py spd.bin

# From hex bytes:
python spd_dump_parser.py --hex 92 10 0b 01 ...

# Side-by-side comparison of original vs replacement candidate:
python spd_dump_parser.py --compare original.bin replacement.bin
```

## Sample output

```
==============================================================
  SPD EEPROM dump analysis  (JEDEC JC-42.4)
==============================================================
  DRAM type        : DDR3 SDRAM  (byte 3 = 0x0b)
  SPD version      : 1.2
  Data width       : x16   -> FBGA96 (x16)
  Speed grade      : DDR3-1600 (PC3-12800)  (tCKmin = 1250 ps)
  CAS latencies    : [5, 6, 7, 8, 9, 10, 11]
  tAA (CL delay)   : 13.125 ns  (byte 16 = 53)
  tRCD             : 13.125 ns  (byte 18 = 53)
  tRP              : 13.125 ns  (byte 20 = 53)
  tRC              : 46.250 ns  (bytes 21-22 = 165,0)
  Temperature      : standard temperature range only
==============================================================
```

## Capturing a dump

The SPD EEPROM lives at **I2C address 0x50** on the DIMM/module. Any I2C
master works — bus pirate, i2c-tools on Linux, or a microcontroller:

```bash
# Linux / i2c-tools:
i2cdump -y -r 0-127 2 0x50 > spd.bin   # (bus 2, device 0x50)
```

A minimal C snippet for reading 128 bytes over I2C is included in
[`examples/read_spd.c`](examples/read_spd.c).

## Validating a replacement — the short checklist

1. Width and package match (×16 → FBGA96, ×8 → FBGA78).
2. tCKmin → speed grade ≥ original.
3. tAA / tRCD / tRP ≤ original (same or tighter).
4. CAS latency support includes your controller's configured CL.
5. Temperature grade covers the enclosure's worst case.

Loongtion documents verified replacements for common discontinued parts
(e.g. [MT41K128M16JT → YZ38E16SBB](https://www.loongtion.com/cross-reference/micron-mt41k128m16jt-125it-k.html))
with the same FBGA96 footprint, dual 1.35V/1.5V support, and wide-temp
(−40°C to +85°C) or GJB-STD extreme (−55°C to +105°C) grades.

---

## License

MIT — use it, fork it, PR it. If you find a bug, open an issue.

*Loongtion — industrial memory, documented cross-reference, five-year
supply commitment. <https://www.loongtion.com>*
