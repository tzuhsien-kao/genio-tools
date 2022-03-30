# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import errno
import logging
import subprocess
import sys
import pathlib
import platform

import aiot
import aiot.image

if platform.system() == 'Linux':
    import pyudev

def udev_wait():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="usb")

    for action, device in monitor:
        if 'ID_VENDOR_ID' in device and 'ID_MODEL_ID' in device:
            if device['ID_VENDOR_ID'] == '0e8d':
                if action == 'bind':
                    break

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

    def setup_parser(self):
        self.parser.add_argument('targets', type=str, nargs='*',
            help='Name of the partition or group of partition to flash')
        self.parser.add_argument('-P', '--path', type=str, help='Path to image',
            default=".")
        self.parser.add_argument('--dry-run', action="store_true")

        group = self.parser.add_argument_group('Bootstrap')
        group.add_argument('--skip-bootstrap', action="store_true",
            help="Don't bootstrap the board")
        group.add_argument('--bootstrap', type=str, default='lk.bin',
            metavar='lk.bin',
            help='bootstrap binary used for flashing (default: lk.bin)')
        group.add_argument('--bootstrap-addr', type=int, default=0x201000,
            metavar='0x201000',
            help='Address where the bootstrap binary will be loaded (default: 0x201000)')
        group.add_argument('--bootstrap-mode', type=str, default='aarch64',
                           choices=['aarch64', 'aarch32'])

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

        if not args.dry_run and platform.system() == 'Linux':
            try:
                board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                          args.gpio_power, args.gpio_chip)
                board.download_mode_boot()
            except Exception as e:
                self.logger.warning(str(e))

        if not args.skip_bootstrap and not args.dry_run:
            bootrom_app = [
                'aiot-bootrom',
                '--bootstrap', args.path + '/' + args.bootstrap,
                '--bootstrap-addr', hex(args.bootstrap_addr),
                '--bootstrap-mode', args.bootstrap_mode,
            ]
            try:
                if platform.system() == 'Linux':
                    udev_wait()
                subprocess.run(bootrom_app, check=True)
            except KeyboardInterrupt:
                pass

        flasher = aiot.Flash(image, dry_run=args.dry_run)
        flasher.flash(args.targets)

def main():
    tool = FlashTool()
    tool.execute()
