# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import random
import zlib
import struct

class UBootEnv:
    def __init__(self, env_size, env_file, args, use_android_dtbo=False):
        self.logger = logging.getLogger('aiot')
        self.env = [];
        self.env_size = env_size
        self.args = args
        self.use_android_dtbo = use_android_dtbo
        with open(env_file, "r") as env:
            self.env = env.readlines()
        if self.args.dtbo_index:
            if self.use_android_dtbo:
                self.add("adtbo_idx", self.args.dtbo_index)
            else:
                self.add("dtbo_index", self.args.dtbo_index)
        if self.args.serialno:
            self.add("serial#", self.args.serialno)

    def add(self, name, value):
        self.env.append("{}={}".format(name, value))

    def update_env_list(self, uboot_env_set):
        '''
        Takes a list of "KEY=VALUE" string and update/add u-boot env vars
        accordings. This is primarily for the --uboot-env-set arg.
        '''
        if not uboot_env_set:
            return
        for pair in uboot_env_set:
            try:
                k, v = pair.split("=")
                if not self.update(k, v):
                    self.add(k, v)
                    self.logger.info(f"Adding new uboot env: {k}={v}")
            except ValueError:
                self.logger.warn(f"Skipped malformed uboot env pair: '{pair}'")

    def update(self, name, value):
        new_env = []
        updated = False
        for line in self.env:
            if line.startswith(name + '='):
                new_env.append("{}={}".format(name, value))
                updated = True
            else:
                new_env.append(line)
        self.env = new_env
        return updated

    def write_env(self, out, redund_id=-1):
            if self.env_size <= 0:
                raise ValueError("Invalid U-Boot env size")

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
        for line in self.env:
            self.logger.debug(f"(env) {line.strip()}")

        with open(filename, "w+b") as out:
            redund_id = -1

            if redund_offset != -1:
                redund_id = 0

            self.write_env(out, redund_id)

            if redund_offset == -1:
                return

            if redund_offset < self.env_size:
                self.logger.error(f"redund_offset(0x{redund_offset:08x}) < env_size(0x{self.env_size:08x}): the redund env will override the main env, aborting...")
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
