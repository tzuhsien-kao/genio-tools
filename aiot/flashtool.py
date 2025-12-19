# SPDX-License-Identifier: MIT
# Copyright 2024 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import logging
import platform
import signal
import threading
import aiot
import aiot.image

from aiot.bootrom import add_bootstrap_group
from aiot.bootrom import run_bootrom
from aiot.flash_daemon import GenioFlashDaemon
from aiot.flash_worker import bootrom_log_parser
from collections import OrderedDict


if platform.system() == 'Linux':
    import pyudev

# Supported image types
# Raw images should match last, so use an ordered dict
images = OrderedDict([
    ('Yocto', aiot.image.YoctoImage),
    ('Android', aiot.image.AndroidImage),
    ('Ubuntu', aiot.image.UbuntuImage),
    ('BootFirmware', aiot.image.BootFirmwareImage),
    ('Raw', aiot.image.RawImage), 
])

app_description = """
    Genio flashing tool

    This tool is used to flash images.
"""

class FlashTool(aiot.App):
    def __init__(self):
        super().__init__(description=app_description)
        self.setup_parser()

    def add_uboot_group(self, parser):
        # Add U-Boot related arguments to the parser.
        group = parser.add_argument_group('U-Boot')
        group.add_argument('--uboot-env-size',
            default = 0,
            type = lambda num: int(num, 0),
            help = 'Size of the U-Boot environment storage in bytes. By default auto-detect from fw_env.config. Fallback to 4096 bytes if fails.')
        group.add_argument('--uboot-env-redund-offset',
            default = -1,
            type = lambda num: int(num, 0),
            help = 'Enable U-Boot redundant env generation and assign offset of the redundant data. No redundant env by default.')
        group.add_argument('--serialno', type=str, \
            help='Customize "serial#" U-Boot environment variable. '
                'This sets serial number in adb, fastboot, and dmidecode. '
                'Note that this different from the serial used in `genio-board -s` and `genio-flash -s`.')
        group.add_argument('-e', '--uboot-env-set',
            action="append",
            metavar="KEY=VALUE",
            help='Update or add U-Boot env variables as a KEY=VALUE pair. e.g. `-e boot_targets=ebbr -e ethaddr=00:11:22:33:44:55.'
                 'Use double quote for VALUE if there are space characters, e.g. `-e boot_prefixes="/ /boot /oemboot"`.')

    def add_gpio_arguments(self, group):
        # Add GPIO related arguments to the specified group.
        group.add_argument('-r', '--gpio-reset', type=int, default=1, help='GPIO to use to reset the SoC')
        group.add_argument('-d', '--gpio-download', type=int, default=2, help='GPIO to use to put the SoC in download mode (KPCOL0 pin)')
        group.add_argument('-p', '--gpio-power', type=int, default=0, help='GPIO to use to power on the SoC')

    def setup_parser(self):
        # Setup command line argument parser.
        self.parser.add_argument('targets', type=str, nargs='*', help='Name of the partition or group of partition to flash')
        self.parser.add_argument('--dry-run', action="store_true")
        self.parser.add_argument('--skip-erase', action="store_true",
            help='Skip erasing partitions before flash')
        self.parser.add_argument('--daemon', action="store_true", help="Run as a daemon")
        self.parser.add_argument('--workers', type=int, default=2, help='Number of workers in daemon mode')
        self.parser.add_argument('--host', type=str, default='localhost', help='Daemon host address')
        self.parser.add_argument('--port', type=int, help='Socket port for daemon mode')

        # Bootstrap
        add_bootstrap_group(self.parser)
        self.add_uboot_group(self.parser)

        if platform.system() == 'Linux':
            group = self.parser.add_argument_group('Board Control (using libgpiod)')
            group.add_argument('-c', '--gpio-chip', type=int, help='GPIOChip device')
            self.add_gpio_arguments(group)
        elif platform.system() == 'Windows':
            group = self.parser.add_argument_group('Board Control (using ftd2xx driver)')
            group.add_argument('-c', '--ftdi-serial', '-s', type=str, default=None, help='Serial number of the board control COM port. This should be the serial reported by "aiot-board list".')
            self.add_gpio_arguments(group)

        # Setup image-specific arguments
        for name, image in images.items():
            image.define_local_parser(self.parser)
            image_group = self.parser.add_argument_group(name)
            image.setup_parser(image_group)

    def execute(self):
        # Execute the flashing process based on parsed arguments.
        args = super().execute()
        image = self.detect_image(args)

        if image is None:
            self.logger.error("No image found")
            return

        print(image)

        if args.daemon:
            self.run_daemon(image, args)
        else:
            self.run_worker(image, args)

    def detect_image(self, args):
        # Detect the appropriate image based on the provided path.
        for name, img in images.items():
            self.logger.debug(f"Detecting image type: {name}")
            if img.detect(args.path):
                image = img(args)
                image.setup_local_parser()
                return image
        return None

    def run_daemon(self, image, args):
        # Starts the daemon process and worker threads.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        # Launch daemon mode
        daemon = GenioFlashDaemon(args, image)
        # Cleanup legacy aiot tools
        daemon.cleanup_aiot_tools()

        worker_thread = threading.Thread(target=daemon.start_workers)
        worker_thread.start()
        daemon.run()
        worker_thread.join()

    def run_worker(self, image, args):
        # Run the flashing process in worker mode.
        # Note: We need to initialize the Flash class before calling `worker_thread` to avoid creating two instances in a single process.
        from aiot.flash import Flash
        flasher = Flash(image=image, dry_run=args.dry_run, daemon=False, verbose=args.verbose, skip_erase=args.skip_erase)
        flasher.flash_worker(image=image, args=args)

def main():
    # Main entry point for the 'genio-flash'.
    tool = FlashTool()
    tool.execute()
