# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import platform
import signal
import threading

import aiot
import aiot.image

from aiot.bootrom import add_bootstrap_group
from .flash_worker import Flash
from .flash_daemon import GenioFlashDaemon

if platform.system() == 'Linux':
    import pyudev

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
        self.parser.add_argument('targets', type=str, nargs='*', help='Name of the partition or group of partition to flash')
        self.parser.add_argument('--dry-run', action="store_true")
        self.parser.add_argument('--daemon', action="store_true", help="Run as a daemon")
        self.parser.add_argument('--workers', type=int, default=2, help='Number of workers in daemon mode')
        self.parser.add_argument('--host', type=str, default='localhost', help='Daemon host address')
        self.parser.add_argument('--port', type=int, help='Socket port for daemon mode')

        # Bootstrap
        add_bootstrap_group(self.parser)
        self.add_firmware_group(self.parser)
        self.add_uboot_group(self.parser)

        def add_gpio_arguments(group):
            group.add_argument('-r', '--gpio-reset', type=int, default=1, help='GPIO to use to reset the SoC')
            group.add_argument('-d', '--gpio-download', type=int, default=2, help='GPIO to use to put the SoC in download mode (KPCOL0 pin)')
            group.add_argument('-p', '--gpio-power', type=int, default=0, help='GPIO to use to power on the SoC')

        if platform.system() == 'Linux':
            group = self.parser.add_argument_group('Board Control (using libgpiod)')
            group.add_argument('-c', '--gpio-chip', type=int, help='GPIOChip device')
            add_gpio_arguments(group)

        elif platform.system() == 'Windows':
            group = self.parser.add_argument_group('Board Control (using ftd2xx driver)')
            group.add_argument('-c', '--ftdi-serial', '-s', type=str, default=None, help='Serial number of the board control COM port. This should be the serial reported by "aiot-board list".')
            add_gpio_arguments(group)

        for name, image in images.items():
            image.define_local_parser(self.parser)
            image_group = self.parser.add_argument_group(name)
            image.setup_parser(image_group)

    def execute(self):
        image = None

        args = super().execute()

        for name, img in images.items():
            if img.detect(args.path):
                image = img(args)
                image.setup_local_parser()
                break

        if image is None:
            logging.error("No image found")
            return

        print(image)

        if args.daemon:
            self.run_daemon(image, args)
        else:
            self.run_worker(image, args)

    def run_daemon(self, image, args):
        """Starts the daemon process and a worker processes."""
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
        # We need to initialize the Flash class before calling `worker_thread` to avoid creating two instances in a single process.
        flasher = Flash(image=image, dry_run=args.dry_run, daemon=False, verbose=args.verbose)
        flasher.flash_worker(image=image, args=args)

def main():
    tool = FlashTool()
    tool.execute()

if __name__ == "__main__":
    main()