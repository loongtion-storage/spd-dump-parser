#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_sample_spd.py — 生成测试用样例 SPD dump
（字节值按 JEDEC DDR3 SPD 编码，用于本地验证 parser；非真实器件 dump）
"""
import struct
import sys


def make_ddr3(tck_ps, width, cl_mask14, b16_taa, b18_trcd, b20_trp, temp_ext=False):
    b = bytearray(128)
    b[0] = 0x92        # SPD 128 bytes
    b[1] = 0x20        # SPD 1.x
    b[2] = 0x12        # SPD revision 1.2
    b[3] = 0x0B        # DDR3 SDRAM
    b[4] = 0x30        # density 4Gb (bits 7..4 = 3 -> 4096 Mb)
    b[5] = 0x00
    b[6] = 0x00
    b[7] = 0x00
    b[8] = 0x01 if width == 16 else 0x00   # width 16 -> x16, 0 -> x8
    # tCKmin: 2 bytes, low 6 bits of byte12 << 8 | byte13
    b[12] = (tck_ps >> 8) & 0x3F
    b[13] = tck_ps & 0xFF
    # CAS latency masks: bytes 14..17
    b[14] = cl_mask14 & 0x7F
    b[15] = 0x00
    # tAA / tRCD / tRP in 0.25 ns units
    b[16] = int(b16_taa * 4)
    b[18] = int(b18_trcd * 4)
    b[20] = int(b20_trp * 4)
    # tRC = bytes 21 (lo 8 bits) + 22 (hi 4 bits), 0.25 ns units
    trc = int(46.25 * 4)
    b[21] = trc & 0xFF
    b[22] = (trc >> 8) & 0x0F
    # temp range byte 30: bit5 = extended temp range
    if temp_ext:
        b[30] |= 0x20
    # checksum byte 63 (1's complement sum of bytes 0..62)
    s = sum(b[0:63]) & 0xFF
    b[63] = (256 - s) & 0xFF
    return bytes(b)


def main():
    # DDR3-1600 x16, CL 5-11, tAA/tRCD/tRP = 13.125ns (DDR3-1600 11-11-11)
    spd_1600_x16 = make_ddr3(1250, 16, 0x7F, 13.125, 13.125, 13.125)
    with open("sample_ddr3_1600_x16.bin", "wb") as f:
        f.write(spd_1600_x16)
    # DDR3-800 x8, slower timings
    spd_800_x8 = make_ddr3(2500, 8, 0x1F, 15.0, 15.0, 15.0)
    with open("sample_ddr3_800_x8.bin", "wb") as f:
        f.write(spd_800_x8)
    print("wrote sample_ddr3_1600_x16.bin (128B)")
    print("wrote sample_ddr3_800_x8.bin (128B)")


if __name__ == "__main__":
    main()
