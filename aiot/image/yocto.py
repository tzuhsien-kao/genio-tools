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
import traceback
import argparse

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
        self.kernel_dtbs = None
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

                # avoid duplicated entries, kernel_dtbo_autoload may be already
                # populated by u-boot-initial-env
                if dtbo not in self.kernel_dtbo_autoload:
                    self.kernel_dtbo_autoload.append(dtbo)

        # remove all --unload_dtbo items
        if self.args.unload_dtbo:
            self.kernel_dtbo_autoload = list(filter(lambda x: x not in self.args.unload_dtbo, self.kernel_dtbo_autoload))

        if args.interactive:
            self.run_interactive_mode()

    def generate_file(self, partition, filename):
        if filename == 'u-boot-env.bin':
            self.generate_uboot_env()

    def run_interactive_mode(self):
        for dtbo in self.kernel_dtbo:
            while True:
                try:
                    is_auto_load = dtbo in self.kernel_dtbo_autoload
                    if is_auto_load:
                        prompt = "[Y/n]"
                    else:
                        prompt = "[N/y]"

                    choice = input(f"Load overlay '{dtbo} {prompt}:").lower()
                    if choice == 'y':
                        self.kernel_dtbo_autoload.append(dtbo)
                        break
                    elif choice == 'n':
                        if is_auto_load:
                            self.kernel_dtbo_autoload.remove(dtbo)
                        break
                    else:
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
            self.logger.error("Your installation of Genio tools is too old. "
                f"Please upgrade to version {min_version} or "
                "higher")
            sys.exit(-errno.ENOENT)

    def load_initial_dtbo(self):
        # Parse pre-defined dtbo list in u-boot-initial-env
        # by setting KERNEL_DEVICETREE_OVERLAYS_AUTOLOAD options
        # in Yocto's local.conf
        initial_dtbo = set()
        with open(os.path.join(self.path, 'u-boot-initial-env'), 'r') as fp:
            config_string = '[config]\n' + fp.read()
            config = configparser.ConfigParser(allow_no_value = True, strict = False)
            config.read_string(config_string)
            # There are 3 possible dtbo loading lists:
            # 1. FIT boot path takes 'boot_conf' in u-boot-env.bin, while
            # 2. EFI boot path takes 'list_dtbo' in u-boot-env.bin;
            # 3. In secure boot scenarios, the one embedded in the U-Boot device tree in fip.bin
            #
            # We only take care of 1 & 2, which allows dyanmic update of dtbo list.
            # These two variables, 'boot_conf' and 'list_dtbo' should be exactly the same,
            # but we extract their union just in case u-boot-initial-env is updated manually.
            try:
                boot_conf_value = config['config'].get('boot_conf', "")
                boot_conf = []
                if boot_conf_value:
                    boot_conf = [d for d in boot_conf_value.split("#conf-") if d.endswith('.dtbo')]

                list_dtbo_value = config['config'].get('list_dtbo', "")
                list_dtbo = []
                if list_dtbo_value:
                    list_dtbo = list_dtbo_value.split(' ')

                self.logger.debug(f"u-boot-initial-env: boot_conf: dtbo={boot_conf}")
                self.logger.debug(f"u-boot-initial-env: list_dtbo: dtbo={list_dtbo}")
                initial_dtbo = set(boot_conf)
                initial_dtbo = initial_dtbo.union(list_dtbo)
            except KeyError:
                self.logger.warn("failed to parse boot_conf or list_dtbo from u-boot-initial-env")
                self.logger.debug(traceback.format_exc())
                initial_dtbo = set()

        for dtbo in initial_dtbo:
            if dtbo not in self.kernel_dtbo:
                self.logger.error(f"'{dtbo}' is assigned in u-boot-initial-env but not available. "
                                  f"Available DTBOs: {self.kernel_dtbo}")
                sys.exit(-1)
            self.kernel_dtbo_autoload.append(dtbo)

    def load_dtbos(self):
        dtbos = list(Path(self.path).glob("devicetree/*.dtbo"))
        self.kernel_dtbo = list(map(lambda dtbo: dtbo.name, dtbos))

    def init(self, path, name, machine):
        self.name = name
        self.machine = machine

        # Check for the file with and without '.rootfs' in the filename
        image_suffix = ".rootfs"
        rootfs_filename = f"{path}/{name}-{machine}{image_suffix}.testdata.json"
        if not os.path.exists(rootfs_filename):
            image_suffix = ""
            rootfs_filename = f"{path}/{name}-{machine}{image_suffix}.testdata.json"
        self.logger.debug(f"Found image suffix: {image_suffix}")

        with open(rootfs_filename, "r") as fp:
            data = json.load(fp)
            self.description = data['DESCRIPTION']
            self.distro = data['DISTRO']
            self.distro_name = data['DISTRO_NAME']
            self.distro_version = data['DISTRO_VERSION']
            if 'DISTRO_CODENAME' in data:
                self.distro_codename = data['DISTRO_CODENAME']
            self.machine = data['MACHINE']
            self.kernel_dtbs = data.get("KERNEL_DEVICETREE","").split(' ')
            self.distro_features = data['DISTRO_FEATURES']

        if (self.args.load_dtbo or self.args.unload_dtbo) and 'secure-boot' in self.distro_features:
            self.logger.warn("Can't use --load-dtbo/--unload-dtbo with secure boot enabled")

        self.load_dtbos()
        self.load_initial_dtbo()
        self.load_config()
        self.check_min_version()

        for partition in self.partitions:
            if not self.partitions[partition]:
                if partition == "rootfs":
                    self.partitions[partition] = f"{name}-{machine}{image_suffix}.ext4"
                elif partition == "mmc0":
                    self.partitions[partition] = f"{name}-{machine}{image_suffix}.wic.img"
                elif partition == "modules":
                    self.partitions[partition] = f"modules-{machine}{image_suffix}.modimg.ext4"

    def detect_uboot_env_size(self):
        '''
        IoT Yocto v22.x - v24.0 is default to 4KiB (0x1000) env size.
        However after v24.1, some images may have larger env size
        due to more complicated boot options. Each board may have
        its own env size settings. So we detect the actual env size
        from fw_env.cfg, which is generated by U-Boot recipe during
        build process.
        '''
        legacy_env_size = 0x1000
        detected_size = 0
        try:
            # Looking for configuration line, which looks like this:
            # /dev/mmcblk0boot1	0x0000		0x1000
            # The first integer is offset, which we ignore for now.
            # The last integer is the size.
            # For the moment we take only '/dev/' and '/boot/' as valid.
            with open(f"{self.path}/fw_env.config", 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    is_dev = line.startswith("/dev/")
                    is_boot = line.startswith("/boot/")
                    if is_dev or is_boot:
                        # set base to '0' to enable auto-detection of hex
                        detected_size = int(line.split()[-1], 0)
                        print("Detected U-Boot env size:", detected_size)
                        return detected_size
        except:
            detected_size = 0
            self.logger.debug(traceback.format_exc())
            self.logger.error(f"Could not detect U-Boot env size, assume {legacy_env_size}")

        return legacy_env_size

    def generate_uboot_env(self):
        args_env_size = self.args.uboot_env_size
        if args_env_size:
            env_size = args_env_size
            print(f"Enforce U-Boot env size: {env_size}")
        else:
            env_size = self.detect_uboot_env_size()
        env = aiot.UBootEnv(env_size,
                            f"{self.path}/u-boot-initial-env",
                            self.args, use_android_dtbo=False)

        env.update_env_list(self.args.uboot_env_set)

        if len(self.kernel_dtbo_autoload) > 0:
            boot_conf = f"#conf-{self.kernel_dtbs[0].replace('/', '_')}"
            list_dtbo = ""
            for dtbo in self.kernel_dtbo_autoload:
                boot_conf += f"#conf-{dtbo}"
                list_dtbo += f"{dtbo} "
            if not env.update('boot_conf', boot_conf):
                env.add('boot_conf', boot_conf)
            env.update('list_dtbo', list_dtbo)
        self.logger.debug(f"redund_offset={self.args.uboot_env_redund_offset}")
        env.write_binary(f"{self.path}/u-boot-env.bin", self.args.uboot_env_redund_offset)

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

        images = sorted(list(images))

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
            print("\t( * items are automatically loaded )")

            for dtbo in self.kernel_dtbo:
                status = '*' if dtbo in self.kernel_dtbo_autoload else ' '
                print(f"\t{status} {dtbo}")
            sys.exit(0)

    @classmethod
    def detect(cls, path):
        p = Path(path).absolute()
        manifests = list(p.glob("*.manifest"))
        found = len(manifests) > 0

        if not found:
            logger = logging.getLogger('aiot')
            logger.debug(f"No *.manifest found in: {p}")
            logger.debug(f"Files in path:")
            contents = os.listdir(path)
            logger.debug(contents)

        return found

    @classmethod
    def setup_parser(cls, parser):
        parser.add_argument('-i', '--image', type=str,
            help='Name of the image to flash')
        parser.add_argument('-I', '--interactive', action="store_true",
            help='Interactively select what will be flashed')
        parser.add_argument('--load-dtbo', action="append", type=str,
            help='Name of the dtbo to load')
        parser.add_argument('--unload-dtbo', action="append", type=str,
            help='Name of the dtbo to remove from auto-load list')
        parser.add_argument('--list-dtbo', action="store_true",
            help='Show the list of available DTBO. Auto-load items have asterisk(*).')

    @classmethod
    def define_local_parser(cls, parser):
        cls.parser = argparse.ArgumentParser(parents = [parser], add_help=False)

    @classmethod
    def setup_local_parser(cls):
        cls.setup_parser(cls.parser)
        return cls.parser.parse_args()

    def __str__(self):
        return f"""Genio Tools: v{aiot.version}
Yocto Image:
\tname:     {self.description} ({self.name})
\tdistro:   {self.distro_name} {self.distro_version} ({self.distro})
\tcodename: {self.distro_codename}
\tmachine:  {self.machine}
\toverlays: {self.kernel_dtbo_autoload}
"""
