# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

from pathlib import Path
import configparser
import oyaml

import rity

class AndroidImage:
    def __init__(self, args):
        self.args = args
        self.path = args.path
        self.partitions = {
            "mmc0": "MBR_EMMC",
            "mmc0boot0": "bl2.img",
            "mmc0boot1": "u-boot-env.bin",
            "bootloaders": "fip.bin",
        }
        self.groups = {
            "all": {
                "erase": ["mmc0", "mmc0boot0", "mmc0boot1"],
                "flash": ["mmc0", "mmc0boot0", "mmc0boot1", "bootloaders"],
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
        env = rity.UBootEnv(4096, f"{self.path}/u-boot-initial-env")
        if self.args.dtbo_index:
            env.update("dtbo_index", self.args.dtbo_index)
        env.write_binary(f"{self.path}/u-boot-env.bin")

    @classmethod
    def detect(cls, path):
        p = Path(path) / "android-info.txt"
        return p.exists()

    @classmethod
    def setup_parser(cls, parser):
        parser.add_argument('--dtbo-index', type=str, \
            help='Enable one or multiple DTBO(s)')

    def __str__(self):
        return f"""Android Image:
\tboard:     {self.board}
"""
