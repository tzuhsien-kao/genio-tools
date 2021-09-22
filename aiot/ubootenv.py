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

    def write_env(self, out, redund_id=-1):
            pos = out.tell()

            out.seek(pos + 4)

            if redund_id >= 0:
                out.write(struct.pack("B", redund_id))

            # Write environment
            for line in self.env:
                if line == '\n':
                    continue
                data = line.rstrip("\n").encode() + b'\0'
                out.write(data)

            while out.tell() - pos < self.env_size:
                out.write(chr(0x00).encode())

            # Compute CRC
            out.seek(pos + 4)
            if redund_id >= 0:
                out.seek(pos + 5)

            crc = zlib.crc32(out.read(self.env_size - 4)) & 0xffffffff

            # Write CRC
            out.seek(pos)
            out.write(struct.pack("I", crc))

    def write_binary(self, filename = "u-boot-env.bin", redund_offset=-1):
        with open(filename, "w+b") as out:
            redund_id = -1

            if redund_offset != -1:
                redund_id = 0

            self.write_env(out, redund_id)

            if redund_offset == -1:
                return

            if redund_offset < self.env_size:
                print("redund_offset < env_size: the redund env will override the main env, aborting...")
                return

            out.seek(redund_offset)
            self.write_env(out, 1)

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
