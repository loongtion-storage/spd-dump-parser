/*
 * read_spd.c — minimal I2C read of a DDR3/DDR4 SPD EEPROM (JEDEC JC-42.4)
 *
 * The SPD EEPROM sits at I2C address 0x50 on the module. This example uses
 * the Linux i2c-dev interface; adapt the adapter number for your system.
 *
 * Build:  gcc -o read_spd read_spd.c
 * Run:    ./read_spd /dev/i2c-2 0x50 spd.bin
 *
 * This is demo/snippet code for field engineers — not production firmware.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define SPD_LEN 128 /* DDR3 SPD 1.x is 128 bytes (0x00-0x7F) */

int main(int argc, char *argv[])
{
    if (argc < 3) {
        fprintf(stderr, "usage: %s /dev/i2c-N 0x50 [out.bin]\n", argv[0]);
        return 1;
    }
    const char *dev = argv[1];
    long addr = strtol(argv[2], NULL, 0);
    const char *outpath = argc > 3 ? argv[3] : "spd.bin";

    int fd = open(dev, O_RDWR);
    if (fd < 0) { perror("open i2c"); return 1; }
    if (ioctl(fd, I2C_SLAVE, addr) < 0) { perror("i2c slave"); close(fd); return 1; }

    uint8_t buf[SPD_LEN] = {0};
    uint8_t offset = 0x00;

    /* Set the EEPROM read offset, then read back 128 bytes. */
    if (write(fd, &offset, 1) != 1) { perror("set offset"); close(fd); return 1; }
    if (read(fd, buf, SPD_LEN) != SPD_LEN) { perror("read spd"); close(fd); return 1; }
    close(fd);

    FILE *f = fopen(outpath, "wb");
    if (!f) { perror("out file"); return 1; }
    fwrite(buf, 1, SPD_LEN, f);
    fclose(f);

    printf("SPD dump (%d bytes) written to %s\n", SPD_LEN, outpath);
    return 0;
}
