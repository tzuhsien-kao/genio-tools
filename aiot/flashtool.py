# SPDX-License-Identifier: MIT
# Copyright 2024 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import logging
import platform

import aiot
import aiot.image

from aiot.bootrom import run_bootrom, add_bootstrap_group

if platform.system() == 'Linux':
    import pyudev

from os.path import exists

images = {
    'Yocto': aiot.image.YoctoImage,
    'Android': aiot.image.AndroidImage,
    'Ubuntu': aiot.image.UbuntuImage,
}

app_description = """
    Genio flashing tool

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
            help="Customize serial number used in adb and fastboot, e.g. the result of 'adb devices'\n"
                 "This is not the serial used by 'aiot-board -s' and 'aiot-flash -s',"
                 "which is FTDI serial connected to UART0.")

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

        if platform.system() == 'Windows':
            group = self.parser.add_argument_group('Board Control (using ftd2xx driver)')
            group.add_argument('-c', '--ftdi-serial', '-s', type=str, default=None, help='Serial number of the board control COM port. This should be the serial reported by "aiot-board list".')
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

        if not args.dry_run:
            try:
                if platform.system() == 'Linux':
                    board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                            args.gpio_power, args.gpio_chip)
                elif platform.system() == 'Windows':
                    board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                            args.gpio_power, None,
                                            serial = args.ftdi_serial)
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
                self.logger.warning("Board control failed. This might be caused by TTY/COM port being used by another process, "
                                    "such as TeraTerm or Putty on Windows. You could try manually put the board in DOWNLOAD mode. Continue flashing...")
                self.logger.info("Continue flashing...")
        if not args.skip_bootstrap and not args.dry_run:
            run_bootrom(args)

        flasher.flash(args.targets)

def main():
    tool = FlashTool()
    tool.execute()