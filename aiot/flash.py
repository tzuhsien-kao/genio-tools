# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import errno
import logging
import sys
import pathlib
import platform
import os

import aiot
import aiot.image

from aiot.bootrom import run_bootrom, add_bootstrap_group

if platform.system() == 'Linux':
    import pyudev

from os.path import exists

class Flash:
    def __init__(self, image, dry_run=False):
        self.img = image
        self.fastboot = aiot.Fastboot(dry_run=dry_run)
        self.logger = logging.getLogger('aiot')

    def flash_partition(self, partition, filename):
        def has_method(obj, method):
            return callable(getattr(obj, method, None))

        if has_method(self.img, 'generate_file'):
            self.img.generate_file(partition, filename)

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

    def check(self, targets):
        if len(targets) == 0 and 'all' not in self.img.groups:
            self.logger.error("No target specified, and no 'all' default target available")
            return False

        for target in targets:
            partition = target
            binary = None
            if ':' in target:
                partition, binary = target.split(':')

            if target not in self.img.groups and partition not in self.img.partitions:
                self.logger.error(f"Invalid target '{target}'")
                return False

            if partition in self.img.partitions:
                if binary == None:
                    binary = os.path.join(self.img.path, self.img.partitions[partition])

                # u-boot-env.bin will be generated later. Skip checking.
                if os.path.basename(binary) == 'u-boot-env.bin':
                    continue

                if not os.path.exists(binary):
                    self.logger.error(f"The binary file '{binary}' for partition '{partition}' doesn't exist")
                    return False

        return True

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

images = {
    'Yocto': aiot.image.YoctoImage,
    'Android': aiot.image.AndroidImage,
    'Ubuntu': aiot.image.UbuntuImage,
}

app_description = """
    AIoT flashing tool

    This tool is used to flash images.
"""

class FlashTool(aiot.App):
    def __init__(self):
        aiot.App.__init__(self, description=app_description)
        self.setup_parser()

    def add_uboot_group(self, parser):
        group = parser.add_argument_group('U-Boot')
        group.add_argument('--uboot-env-size',
            default = 4096, 
            type = lambda num: int(num, 0),
            help = 'Size of the U-Boot environment storage. Default to 4096 bytes.')
        group.add_argument('--uboot-env-redund-offset', 
            default = -1,
            type = lambda num: int(num, 0),
            help = 'Enable U-Boot redundant env generation and assign offset of the redundant data. No redundant env by default.')
        group.add_argument('-e', '--uboot-env-set',
            action="append",
            metavar="KEY=VALUE",
            help='Update or add U-Boot env variables as a KEY=VALUE pair. e.g. `-e boot_targets=ebbr -e ethaddr=00:11:22:33:44:55.'
                 'Use double quote for VALUE if there are space characters, e.g. `-e boot_prefixes="/ /boot /oemboot"`.')

    def add_firmware_group(self, parser):
        group = parser.add_argument_group('Firmware')
        group.add_argument('--serialno', type=str, \
            help='Customize serial number used by adb/fastboot')

    def setup_parser(self):
        self.parser.add_argument('targets', type=str, nargs='*',
            help='Name of the partition or group of partition to flash')
        self.parser.add_argument('--dry-run', action="store_true")

        # Bootstrap
        add_bootstrap_group(self.parser)

        self.add_firmware_group(self.parser)
        self.add_uboot_group(self.parser)

        if platform.system() == 'Linux':
            group = self.parser.add_argument_group('Board Control (using libgpiod)')
            group.add_argument('-c', '--gpio-chip', type=int, help='GPIOChip device')
            group.add_argument('-r', '--gpio-reset', type=int, default=1,
                help='GPIO to use to reset the SoC')
            group.add_argument('-d', '--gpio-download', type=int, default=2,
                help='GPIO to use to put the SoC in download mode (KPCOL0 pin)')
            group.add_argument('-p', '--gpio-power', type=int, default=0,
                help='GPIO to use to power on the SoC')

        for name, image in images.items():
            image.define_local_parser(self.parser)

        for name, image in images.items():
            image_group = self.parser.add_argument_group(name)
            image.setup_parser(image_group)

    def execute(self):
        image = None
        chip = None

        args = super().execute()

        for name, img in images.items():
            if img.detect(args.path):
                image = img(args)
                image.setup_local_parser()
                break

        if image is None:
            self.logger.error("No image found")
            return

        print(image)

        flasher = aiot.Flash(image, dry_run=args.dry_run)
        if not flasher.check(args.targets):
            return

        if not args.dry_run and platform.system() == 'Linux':
            try:
                board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                          args.gpio_power, args.gpio_chip)
                board.download_mode_boot()
            except RuntimeError as r:
                self.logger.warning(r)
                self.logger.warning("Unable to find and reset the board. Possible causes are:\n"
                                    "1. This is not a Genio 350/700 EVK, nor a Pumpkin board.\n"
                                    "2. The board port UART0 is not connected.\n"
                                    "3. The UART0 port is being opened by another tool, such as TeraTerm on Windows.\n"
                                    "You can now manually reset the board into DOWNLOAD mode.\n")
                self.logger.info("Continue flashing...")
            except Exception as e:
                self.logger.warning(str(e))
                self.logger.warning("Board control failed. You could try manually put the board in DOWNLOAD mode.")
                self.logger.info("Continue flashing...")

        if not args.skip_bootstrap and not args.dry_run:
            run_bootrom(args)

        flasher.flash(args.targets)

def main():
    tool = FlashTool()
    tool.execute()
