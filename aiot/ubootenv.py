# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import random
import zlib
import struct

class UBootEnv:
    def __init__(self, env_size, env_file):
        self.env = [];
        self.env_size = env_size
        with open(env_file, "r") as env:
            self.env = env.readlines()

    def add(self, name, value):
        self.env.append("{}={}".format(name, value))

    def update(self, name, value):
        new_env = []
        for line in self.env:
            if line.startswith(name + '='):
                new_env.append("{}={}".format(name, value))
            else:
                new_env.append(line)
        self.env = new_env

    def write_binary(self, filename = "u-boot-env.bin"):
        with open(filename, "w+b") as out:
            out.seek(4)

            # Write environment
            for line in self.env:
                if line == '\n':
                    continue
                data = line.rstrip("\n").encode() + b'\0'
                out.write(data)

            while out.tell() < self.env_size:
                out.write(chr(0x00).encode())

            # Compute CRC
            out.seek(4)
            crc = zlib.crc32(out.read(self.env_size - 4)) & 0xffffffff

            # Write CRC
            out.seek(0)
            out.write(struct.pack("I", crc))

    def gen_mac_addr(self, oui, num_iface):
        for i in range(num_iface):
            macaddr =  "{}:{:02X}:{:02X}:{:02X}".format(
                            oui,
                            random.randint(0, 255),
                            random.randint(0, 255),
                            random.randint(0, 255))
            varname = "eth{}addr".format(i)
            if i == 0:
                varname = "ethaddr"
            self.add(varname, macaddr)
