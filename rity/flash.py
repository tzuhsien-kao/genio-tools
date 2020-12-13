# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import pathlib

import rity

class Flash:
    def __init__(self, image, dry_run=False):
        self.img = image
        self.fastboot = rity.Fastboot(dry_run=dry_run)
        self.logger = logging.getLogger('rity')

    def flash_partition(self, partition, filename):
        path = pathlib.Path(self.img.path) / filename
        self.fastboot.flash(partition, str(path))

    def erase_partition(self, partition):
        self.fastboot.erase(partition)

    def flash_group(self, group):
        actions = self.img.groups[group]
        if 'erase' in actions:
            for partition in actions['erase']:
                if not partition in self.img.partitions:
                    self.logger.error(f"invalid partition {partition}")
                    return
                self.erase_partition(partition)

        if 'flash' in actions:
            for partition in actions['flash']:
                if not partition in self.img.partitions:
                    self.logger.error(f"invalid partition {partition}")
                    return
                self.flash_partition(partition, self.img.partitions[partition])

    def flash(self, targets):
        if len(targets) == 0:
            if 'all' in self.img.groups:
                targets = ["all"]
            else:
                self.logger.error("No target specified, and no 'all' default target available")

        for target in targets:
            partition = target
            binary = None
            if ':' in target:
                partition, binary = target.split(':')

            if target in self.img.groups:
                self.flash_group(target)
                continue

            if partition in self.img.partitions:
                if binary is None:
                    binary = self.img.partitions[target]
                self.flash_partition(partition, binary)
                continue

            self.logger.error(f"target '{target}' does not exists")
#            list targets here
        self.fastboot.reboot()
