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
import packaging.version
import struct
import sys

import aiot

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
        self.logger = logging.getLogger('aiot')
        self.groups = []

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

    def generate_file(self, partition, filename):
        if partition == 'mmc0boot1':
            self.generate_uboot_env()

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

    def load_config(self):
        config_file = f"{self.path}/"
        if os.path.exists(config_file + "rity.json"):
            config_file += "rity.json"
        else:
            config_file += "partitions.json"

        with open(config_file, 'r') as fp:
            data = json.load(fp)
            self.tools_cfg = data.get('rity-tools', None)
            self.partitions = data['partitions']
            if 'groups' in data:
                self.groups = data['groups']

    def check_min_version(self):
        if not self.tools_cfg or not 'min-version' in self.tools_cfg:
            return

        min_version = self.tools_cfg['min-version']

        if packaging.version.parse(min_version) > \
           packaging.version.parse(aiot.version):
            self.logger.error("Your installation of AIoT tools is too old. "
                f"Please upgrade to version {min_version} or "
                "higher")
            sys.exit(-errno.ENOENT)

    def load_dtbos(self):
        dtbos = list(Path(self.path).glob("devicetree/*.dtbo"))
        self.kernel_dtbo = list(map(lambda dtbo: dtbo.name, dtbos))

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
            self.kernel_dtb = data['KERNEL_DEVICETREE']


        self.load_dtbos()
        self.load_config()
        self.check_min_version()

        for partition in self.partitions:
            if not self.partitions[partition]:
                if partition == "rootfs":
                    self.partitions[partition] = f"{name}-{machine}.ext4"
                elif partition == "mmc0":
                    self.partitions[partition] = f"{name}-{machine}.wic.img"

    def generate_uboot_env(self):
        env = aiot.UBootEnv(self.args.uboot_env_size,
                            f"{self.path}/u-boot-initial-env")
        if len(self.kernel_dtbo_autoload) > 0:
            boot_conf = f"#conf-{self.kernel_dtb.replace('/', '_')}"
            list_dtbo = ""
            for dtbo in self.kernel_dtbo_autoload:
                boot_conf += f"#conf-{dtbo}"
                list_dtbo += f"{dtbo} "
            env.update('boot_conf', boot_conf)
            env.update('list_dtbo', list_dtbo)
        env.write_binary(f"{self.path}/u-boot-env.bin")

    def load_env_file(self, env_file):
        with open(env_file, 'r') as fp:
            config_string = '[config]\n' + fp.read()
            config = configparser.ConfigParser()
            config.read_string(config_string)
            name = config['config']['IMAGE_BASENAME'].strip('"')
            machine = config['config']['MACHINE'].strip('"')
            return (name, machine)

    def load_testdata_file(self, testdata_file):
        with open(testdata_file, 'r') as fp:
            data = json.load(fp)
            name = data['PN']
            machine = data['MACHINE']
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
        images = set()

        if len(image_files) > 0:
            for env_file in image_files:
                image = self.load_env_file(env_file)
                images.add(image)
        else:
            image_files = list(Path(path).glob("*.testdata.json"))
            for test_data_file in image_files:
                image = self.load_testdata_file(test_data_file)
                images.add(image)

        images = list(images)

        if len(images) == 0:
            self.logger.error(f"Could not find any Yocto images in directory '{path}'")
            sys.exit(-errno.ENOENT)
        elif len(images) == 1:
            image = images.pop()
        else:
            while True:
                print("Images found:")
                for i,image in enumerate(images):
                    print(f"\t[{i}] {image[0]}")

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
        parser.add_argument('--load-dtbo', action="append", type=str,
            help='Name of the dtbo to load')
        parser.add_argument('--list-dtbo', action="store_true",
            help='Show the list of available DTBO')


    def __str__(self):
        return f"""AIoT Tools: v{aiot.version}
Yocto Image:
\tname:     {self.description} ({self.name})
\tdistro:   {self.distro_name} {self.distro_version} ({self.distro})
\tcodename: {self.distro_codename}
\tmachine:  {self.machine}
\toverlays: {self.kernel_dtbo_autoload}
"""
