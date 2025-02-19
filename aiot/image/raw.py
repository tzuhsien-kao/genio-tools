# SPDX-License-Identifier: MIT
# Copyright (C) 2025 MediaTek Inc.
# Author: Pablo Sun <pablo.sun@mediatek.com>

from pathlib import Path

import binascii
import errno
import json
import logging
import os
import packaging.version
import struct
import sys
import traceback
import argparse
from pathlib import Path

import aiot

class RawImage:
    def __init__(self, args):
        self.args = args
        self.path = Path(args.path)
        self.description = None
        self.name = None
        self.machine = None
        self.tools_cfg = []
        self.groups = []
        self.partitions = []
        self.uboot_env_size = args.uboot_env_size if args.uboot_env_size else 4096
        self.uboot_env_redund_offset = 0x100000 if args.uboot_env_redund_offset == -1 else args.uboot_env_redund_offset
        self.logger = logging.getLogger('aiot')

        self.load_config()

    def load_config(self):
        if type(self).detect_json(self.path):
            return self.load_config_from_json()
        elif type(self).detect_emmc(self.path):
            return self.default_config_emmc()
        elif type(self).detect_ufs(self.path):
            return self.default_config_ufs()
        return False

    @classmethod
    def detect_json(cls, path):
        config_file = Path(path) / "raw_image.json"
        return config_file.exists()

    def load_config_from_json(self):
        config_file = self.path / "raw_image.json"
        with open(config_file, 'r') as fp:
            data = json.load(fp)

            self.name = data.get('name')
            self.description = data.get('description')
            self.machine = data.get('machine')
            self.tools_cfg = data.get('genio-tools', None)

            if not 'partitions' in data:
                self.logger.error(f"No partition layout found in {config_file}")
                sys.exit(-errno.ENODATA)

            self.partitions = data['partitions']

            if 'groups' in data:
                self.groups = data['groups']

        return True

    @classmethod
    def detect_emmc(cls, path):
        path = Path(path)
        # The default values are taken from
        # the internal document
        # "Converting Android Image to RAW Image and Flashing Using Public Tool v1.0"
        # These are the file names converted from the internal tool.
        emmc_default_files = [
            path / "mmc0.bin",
            path / "mmc0boot0.bin",
            path / "mmc0boot1.bin",
        ]

        # every default file must exist to be valid
        return all([f.exists() for f in emmc_default_files])

    def default_config_emmc(self):
        self.name = "Sparse Image"
        self.description = "eMMC Disk Image"
        self.machine = "Unspecified"
        self.partitions = {
            "mmc0": "mmc0.bin",
            "mmc0boot0": "mmc0boot0.bin",
            "mmc0boot1": "mmc0boot1.bin",
        }
        self.groups = {
            "all": {
                "erase": ["mmc0", "mmc0boot0", "mmc0boot1"],
                "flash": ["mmc0", "mmc0boot0", "mmc0boot1"],
            },

            "erase-mmc": {
                "erase": ["mmc0", "mmc0boot0", "mmc0boot1"],
            },
        }
        return True

    @classmethod
    def detect_ufs(cls, path):
        path = Path(path)
        # The default values are taken from
        # the internal document
        # "Converting Android Image to RAW Image and Flashing Using Public Tool v1.0"
        # These are the file names converted from the internal tool.
        ufs_default_files = [
            path / "ufs_lu2.bin",
            path / "ufs_lu0_lu1.bin",
        ]

        # every default file must exist to be valid
        return all([f.exists() for f in ufs_default_files])

    def default_config_ufs(self):
        self.name = "Sparse Image"
        self.description = "UFS Disk Image"
        self.machine = "Unspecified"

        # Caveat: the download agent (lk.bin) reports UFS paritions
        # as "mmc0", "mmc0boot0" rather than "lu"
        self.partitions = {
            "mmc0": "ufs_lu2.bin",
            "mmc0boot0": "ufs_lu0_lu1.bin",
            "mmc0boot1": "ufs_lu0_lu1.bin",
        }
        self.groups = {
            "all": {
                "erase": ["mmc0", "mmc0boot0", "mmc0boot1"],
                "flash": ["mmc0", "mmc0boot0", "mmc0boot1"],
            },

            "erase-ufs": {
                "erase": ["mmc0", "mmc0boot0", "mmc0boot1"],
            },

            "erase-mmc": {
                "erase": ["mmc0", "mmc0boot0", "mmc0boot1"],
            },
        }
        return True

    @classmethod
    def detect(cls, path):
        json = cls.detect_json(path)
        emmc = cls.detect_emmc(path)
        ufs = cls.detect_ufs(path)
        logging.debug(f"Detect raw image: json={json} emmc={emmc} ufs={ufs}")
        return json or emmc or ufs

    @classmethod
    def setup_parser(cls, parser):
        pass

    @classmethod
    def define_local_parser(cls, parser):
        cls.parser = argparse.ArgumentParser(parents=[parser], add_help=False)

    @classmethod
    def setup_local_parser(cls):
        cls.setup_parser(cls.parser)
        return cls.parser.parse_args()

    def __str__(self):
        return f"""Genio Tools: v{aiot.version}
Raw Image:
\tname:  {self.description} ({self.name})
\tmachine:  {self.machine}
"""