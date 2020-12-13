# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

from pathlib import Path

import binascii
import configparser
import errno
import json
import logging
import os
import struct
import sys

import rity

class YoctoImage:
    def __init__(self, args):
        self.args = args
        self.path = args.path
        self.description = None
        self.distro = None
        self.distro_name = None
        self.distro_version = None
        self.distro_codename = None
        self.name = None
        self.machine = None
        self.kernel_dtbo = None
        self.kernel_dtbo_autoload = []
        self.kernel_dtb = None
        self.logger = logging.getLogger('rity')

        if args.image:
            self.load_image_by_name(args.path, args.image)
        else:
            self.load_image(args.path)

        if self.args.load_dtbo:
            for dtbo in self.args.load_dtbo:
                if dtbo not in self.kernel_dtbo:
                    self.logger.error(f"'{dtbo}' is not available. "
                                      f"Available DTBOs: {self.kernel_dtbo}")
                    sys.exit(-1)
                self.kernel_dtbo_autoload.append(dtbo)

        if args.interactive:
            self.run_interactive_mode()

        self.generate_uboot_env()
        self.generate_partition_table()

    def run_interactive_mode(self):
        for dtbo in self.kernel_dtbo:
            if dtbo in self.kernel_dtbo_autoload:
                continue

            while True:
                try:
                    choice = input(f"Load overlay '{dtbo} [N/y]:").lower()
                    if choice == 'y':
                        self.kernel_dtbo_autoload.append(dtbo)
                        break
                    elif choice == 'n' or choice == '':
                        break
                except KeyboardInterrupt:
                    sys.exit(0)
                except:
                    pass
        print()

    def load_partitions(self):
        with open(f"{self.path}/partitions.json", 'r') as fp:
            data = json.load(fp)
            self.partitions = data['partitions']
            self.groups = data['groups']

    def init(self, path, name, machine):
        self.name = name
        self.machine = machine

        with open(f"{path}/{name}-{machine}.testdata.json", 'r') as fp:
            data = json.load(fp)
            self.description = data['DESCRIPTION']
            self.distro = data['DISTRO']
            self.distro_name = data['DISTRO_NAME']
            self.distro_version = data['DISTRO_VERSION']
            self.distro_codename = data['DISTRO_CODENAME']
            self.machine = data['MACHINE']
            self.kernel_dtbo = data['KERNEL_DEVICETREE_OVERLAYS'].split()
            self.kernel_dtb = data['KERNEL_DEVICETREE']

        self.load_partitions()
        for partition in self.partitions:
            if not self.partitions[partition]:
                self.partitions[partition] = f"{name}-{machine}.ext4"

    def generate_partition_table(self):
        wic_image = f"{self.path}/{self.name}-{self.machine}.wic"
        if os.path.exists(wic_image):
            # extract MBR
            with open(f"{self.path}/MBR_EMMC", "wb+") as mbr:
                with open(wic_image, "rb+") as fd:
                    for blk_id in range(0, 34):
                        mbr.write(fd.read(512))

                # Remove Backup GPT
                mbr.seek(544)
                mbr.write(b'\x01\x00\x00\x00')
                mbr.seek(528)
                mbr.write(b'\x00\x00\x00\x00')
                mbr.seek(512)
                hdr_crc32 = binascii.crc32(mbr.read(92))
                mbr.seek(528)
                mbr.write(struct.pack("<I", hdr_crc32))

    def generate_uboot_env(self):
        env = rity.UBootEnv(self.args.uboot_env_size,
                            f"{self.path}/u-boot-initial-env")
        if len(self.kernel_dtbo_autoload) > 0:
            boot_conf = f"#conf@{self.kernel_dtb.replace('/', '_')}"
            for dtbo in self.kernel_dtbo_autoload:
                boot_conf += f"#conf@{dtbo}"
            env.update('boot_conf', boot_conf)
        env.write_binary(f"{self.path}/u-boot-env.bin")

    def load_env_file(self, env_file):
        with open(env_file, 'r') as fp:
            config_string = '[config]\n' + fp.read()
            config = configparser.ConfigParser()
            config.read_string(config_string)
            name = config['config']['IMAGE_BASENAME'].strip('"')
            machine = config['config']['MACHINE'].strip('"')
            return (name, machine)

    def load_image_by_name(self, path, name):
        image = Path(path) / f"{name}.env"

        if not image.exists():
            self.logger.error(f"{name} image does not exists")
            sys.exit(-errno.ENOENT)

        unused, machine = self.load_env_file(image)
        self.init(path, name, machine)

    def load_image(self, path):
        image_files = list(Path(path).glob("*.env"))
        images = []

        for env_file in image_files:
            image = self.load_env_file(env_file)
            images.append(image)

        if len(images) == 0:
            self.logger.error(f"Could not find any Yocto images in directory '{path}'")
            sys.exit(-errno.ENOENT)
        elif len(images) == 1:
            image = images[0]
        else:
            while True:
                print("Images found:")
                for i in range(len(images)):
                    print(f"\t[{i}] {images[i][0]}")

                try:
                    choice = input("Choice: ")
                    n = int(choice)
                    if n >= 0 and n < len(images):
                        image = images[n]
                        break

                    print()
                    print(f"Invalid choice '{n}'")
                except KeyboardInterrupt:
                    sys.exit(0)
                except:
                    pass

        self.init(path, image[0], image[1])

        if self.args.list_dtbo:
            print("List of available DTBO:")
            for dtbo in self.kernel_dtbo:
                print(f"\t- {dtbo}")
            sys.exit(0)

    @classmethod
    def detect(cls, path):
        manifests = list(Path(path).glob("*.manifest"))
        return len(manifests) > 0

    @classmethod
    def setup_parser(cls, parser):
        parser.add_argument('-i', '--image', type=str,
            help='Name of the image to flash')
        parser.add_argument('--uboot-env-size', default = 4096, type = int, \
            help = 'Size of the U-Boot environment storage')
        parser.add_argument('-I', '--interactive', action="store_true",
            help='Interactively select what will be flashed')
        parser.add_argument('--load-dtbo', action="extend", nargs="+", type=str,
            help='Name of the dtbo to load')
        parser.add_argument('--list-dtbo', action="store_true",
            help='Show the list of available DTBO')


    def __str__(self):
        return f"""Yocto Image:
\tname:     {self.description} ({self.name})
\tdistro:   {self.distro_name} {self.distro_version} ({self.distro})
\tcodename: {self.distro_codename}
\tmachine:  {self.machine}
\toverlays: {self.kernel_dtbo_autoload}
"""
