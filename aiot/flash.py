# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import logging
import pathlib
import platform
import time
import os
import json

import aiot

from aiot.bootrom import run_bootrom
from aiot.bootrom_log_parser import bootrom_log_parser

class Flash:
    def __init__(self, image, dry_run=False, daemon=False, verbose=False, queue=None, data_event=None, skip_erase=False):
        # Initialize the Flash object with necessary parameters.
        self.img = image
        self.daemon = daemon
        self.verbose = verbose
        self.queue = queue
        self.fastboot_sn = None
        self.data_event = data_event
        self.skip_erase = skip_erase
        self.fastboot = aiot.Fastboot(dry_run=dry_run, daemon=daemon)
        self.logger = logging.getLogger('aiot')

    def handle_output(self, json_output):
        # Handle the output from the flash operation.
        if self.queue:
            self.queue.put(json_output)
            if self.data_event:
                self.data_event.set()  # Notify the flash daemon

    def flash_partition(self, partition, filename):
        # Flash a specific partition with the given filename.
        if hasattr(self.img, 'generate_file'):
            self.img.generate_file(partition, filename)

        path = pathlib.Path(self.img.path) / filename

        if self.daemon:
            process = self.fastboot.flash(partition, str(path), self.handle_output, fastboot_sn=self.fastboot_sn)
            if process:
                process.wait()
        else:
            print(f"flashing {partition}={filename}")
            self.fastboot.flash(partition, str(path))

    def erase_partition(self, partition):
        # Erase a specific partition.
        if self.daemon:
            json_output = self.fastboot.erase(partition, fastboot_sn=self.fastboot_sn)
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set()  # Notify the flash daemon
        else:
            print(f"erasing {partition}")
            self.fastboot.erase(partition)

    def flash_group(self, group):
        # Flash a group of partitions defined in the image.
        actions = self.img.groups.get(group, {})
        if self.daemon:
            timeout = 10
            start_time = time.time()

            while not self.fastboot.devices():
                if time.time() - start_time > timeout:
                    data = {'action': 'Error: Jump DA failed', 'error': 'Jump DA: Exceeded 10 seconds.'}
                    json_output = json.dumps(data, indent=4)
                    if self.queue:
                        self.queue.put(json_output)
                        if self.data_event:
                            self.data_event.set()  # Notify the flash daemon
                    break
                time.sleep(1)

            # Assign fastboot serial number
            self.fastboot_sn = self.daemon.assign_sn_flasher(self.fastboot.devices())
            if not self.fastboot_sn: # Abort flash if jump DA failed (Cannot find new fastboot device)
                return

            data = {"fastboot_sn": self.fastboot_sn}
            json_output = json.dumps(data, indent=4)
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set()  # Notify the flash daemon

        for action in ['erase', 'flash']:
            for partition in actions.get(action, []):
                if partition not in self.img.partitions:
                    self.logger.error(f"Invalid partition {partition}")
                    return
                if action == 'erase' and not self.skip_erase:
                    self.erase_partition(partition)
                elif action == 'flash':
                    self.flash_partition(partition, self.img.partitions[partition])

    def check(self, targets):
        # Check if the specified targets are valid for flashing.
        if not targets and 'all' not in self.img.groups:
            self.logger.error("No target specified, and no 'all' default target available")
            return False

        for target in targets:
            partition, binary = (target.split(':') + [None])[:2]

            if target not in self.img.groups and partition not in self.img.partitions:
                self.logger.error(f"Invalid target '{target}'")
                return False

            if partition in self.img.partitions:
                if binary is None:
                    binary = os.path.join(self.img.path, self.img.partitions[partition])

                if os.path.basename(binary) == 'u-boot-env.bin':
                    continue

                if not os.path.exists(binary):
                    self.logger.error(f"The binary file '{binary}' for partition '{partition}' doesn't exist")
                    return False

        return True

    def flash(self, targets):
        # Flash the specified targets.
        if not targets:
            targets = ["all"] if 'all' in self.img.groups else []
            if not targets:
                self.logger.error("No target specified, and no 'all' default target available")
                return

        for target in targets:
            partition, binary = (target.split(':') + [None])[:2]

            if target in self.img.groups:
                self.flash_group(target)
                if self.daemon:
                    if not self.fastboot_sn: # Abort flash if jump DA failed
                        return
                continue

            if partition in self.img.partitions:
                if binary is None:
                    binary = self.img.partitions[target]
                self.flash_partition(partition, binary)
                continue

            self.logger.error(f"target '{target}' does not exist")

        # handling reboot event
        if self.daemon:
            json_output = self.fastboot.reboot(fastboot_sn=self.fastboot_sn)
            self.action = "rebooting"
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set()  # notify flash_daemon
        else:
            self.fastboot.reboot()

    def flash_worker(self, image, args, queue=None, data_event=None):
        # Worker thread that performs the flashing.
        if not self.check(args.targets):
            return

        if args.dry_run:
            self.flash(args.targets)
            return

        result = {"action": "", "error": ""}

        try:
            # Initialize board control based on the operating system
            board = self.initialize_board(args)
            board.download_mode_boot()
        except RuntimeError as r:
            self.handle_board_error(r, args, result, "Unable to find and reset the board.")
        except Exception as e:
            self.handle_board_error(e, args, result, "Board control failed.")

        if not args.skip_bootstrap:
            self.handle_bootstrap(args, queue, data_event)

        self.flash(args.targets)

    def initialize_board(self, args):
        # Initialize the board control based on the OS.
        if platform.system() == 'Linux':
            return aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                    args.gpio_power, args.gpio_chip)
        elif platform.system() == 'Windows':
            return aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                    args.gpio_power, None,
                                    serial=args.ftdi_serial)

    def handle_board_error(self, error, args, result, message):
        # Handle board control errors and log appropriate messages.
        warning_str = (
            f"{message} Possible causes are:\n"
            "1. This is not a Genio 350/700 EVK, nor a Pumpkin board.\n"
            "2. The board port UART0 is not connected.\n"
            "3. The UART0 port is being opened by another tool, such as TeraTerm on Windows.\n"
            "You can now manually reset the board into DOWNLOAD mode.\n"
        )

        if args.daemon:
            if self.queue:
                result["action"] = "Starting"
                result["error"] = f"Board Ctrl: {message} You can check detail with normal single download."
                boardctl_json = json.dumps(result, indent=4)
                self.queue.put(boardctl_json)
                if self.data_event:
                    self.data_event.set()  # notify flash_daemon
        else:
            self.logger.warning(str(error))
            self.logger.warning(warning_str)
            self.logger.info("Continue flashing...")

    def handle_bootstrap(self, args, queue, data_event):
        # Handle the bootstrap process.
        bootrom_output = run_bootrom(args)
        bootrom_json = bootrom_log_parser(bootrom_output)

        if queue:
            queue.put(bootrom_json)
        if data_event:
            data_event.set()  # notify flash_daemon

    def process(self, targets):
        # Main process method to handle flashing tasks.
        if not self.check(targets):
            return

        self.flash(targets)
