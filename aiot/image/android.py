# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

from pathlib import Path
import configparser
import oyaml
import argparse

import aiot

class AndroidImage:
    def __init__(self, args):
        self.args = args
        self.path = args.path
        self.partitions = {
            "mmc0": "MBR_EMMC",
            "mmc0boot0": "mtk-boot.bin",
            "mmc0boot1": "u-boot-env.bin",
            "bootloaders": "bootloaders.img",
        }
        self.groups = {
            "all": {
                "flash": ["mmc0", "mmc0boot0", "mmc0boot1", "bootloaders"],
                "erase_after_flash": ["misc", "metadata"],
            },
        }

        with open(f"{args.path}/android-info.txt", 'r') as info_fp:
            config_string = '[config]\n' + info_fp.read()
            config = configparser.ConfigParser()
            config.read_string(config_string)
            self.board = config['config']['board']

        with open(f"{args.path}/partitions.yaml", 'r') as partitions_file:
            dictionary = oyaml.safe_load(partitions_file)
            partitions = dictionary['partitions']
            for name in partitions:
                partition = partitions[name]
                if 'file' in partition:
                    self.groups["all"]["flash"].append(name)
                    self.partitions[name] = partition['file']

        self.generate_uboot_env()

    def generate_uboot_env(self):
        env = aiot.UBootEnv(8192,
                            f"{self.path}/u-boot-initial-env",
                            self.args)
        env.write_binary(f"{self.path}/u-boot-env.bin")

    @classmethod
    def detect(cls, path):
        p = Path(path) / "android-info.txt"
        return p.exists()

    @classmethod
    def setup_parser(cls, parser):
        parser.add_argument('--dtbo-index', type=str, \
            help='Enable one or multiple DTBO(s)')

    @classmethod
    def define_local_parser(cls, parser):
        cls.parser = argparse.ArgumentParser(parents = [parser], add_help=False)

    @classmethod
    def setup_local_parser(cls):
        cls.setup_parser(cls.parser)
        return cls.parser.parse_args()

    def __str__(self):
        return f"""Android Image:
\tboard:     {self.board}
"""
