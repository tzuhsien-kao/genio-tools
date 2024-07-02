# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import json
import logging
import os
import pathlib
import platform
import re
import threading

import aiot

from aiot.bootrom import run_bootrom
from multiprocessing import Queue, Event

def monitor_thread(worker, image, args, queue, data_event): 
    worker.first_erasing = True

    try:
        while True:
            data_event.wait()
            data_event.clear()
            while not queue.empty():
                data = json.loads(queue.get())
                worker.pid = worker.process.pid

                # update worker's attributes
                for key in ["action", "com_port", "fastboot_sn", "progress", "partition", "error"]:
                    if key in data:
                        setattr(worker, key, data[key])

                # Log based on action and error
                data_str = ', '.join([f'{key}: "{value}"' if key == 'error' else f'{key}: {value}' for key, value in data.items()])
                log_message = f"{worker.com_port}, {worker.fastboot_sn}, {{{data_str}}}"

                if worker.args.verbose:
                    log_message = f"Worker {worker.id}, PID: {worker.pid}, {log_message}"
                else:
                    log_message = f"Worker {worker.id}, {log_message}"

                if worker.action in ["Starting", "Jumping DA", "rebooting"]:
                    worker.logger.info(log_message)
                elif not worker.args.verbose and worker.action == "erasing" and worker.first_erasing:
                    worker.logger.info(f"Worker {worker.id}, {worker.com_port}, {worker.fastboot_sn}, flashing...")
                    worker.first_erasing = False
                elif 'error' in data:
                    worker.logger.warning(log_message)
                else:
                    worker.logger.debug(log_message)

    except json.JSONDecodeError:
        worker.action = "Error"
        output = "Failed to decode JSON output"
    except Exception as e:
        worker.action = "Error"
        output = str(e)

def bootrom_log_parser(log):
    """Parse the bootrom log and convert it to JSON."""
    if log is None:
        return json.dumps({"error": "No log output"}, indent=4)

    result = {
        "action": "",
        "com_port": "",
        "baudrate": "",
        "hw_code": "",
        "address": "",
        "mode": ""
    }

    # Regular expressions to match the required information
    patterns = {
        "com_port": re.compile(r"Opening (\/dev\/ttyACM\d+|COM\d+) using baudrate=(\d+)"),
        "hw_code": re.compile(r"Connected to MediaTek SoC: hw_code\[(0x[0-9a-fA-F]+)\]"),
        "address": re.compile(r"Sending bootstrap to address: (0x[0-9a-fA-F]+)"),
        "jumping": re.compile(r"Jumping to bootstrap at address (0x[0-9a-fA-F]+) in (AArch64) mode")
    }

    # Status messages
    action_messages = {
        "Opening": "Opening",
        "Sending bootstrap": "Sending DA",
        "Jumping to bootstrap": "Jumping DA"
    }

    # Parse the log line by line
    for line in log.splitlines():
        if "Opening" in line:
            result["action"] = action_messages["Opening"]
            match = patterns["com_port"].search(line)
            if match:
                result["com_port"] = match.group(1)
                result["baudrate"] = match.group(2)
        elif "Connected to MediaTek SoC" in line:
            match = patterns["hw_code"].search(line)
            if match:
                result["hw_code"] = match.group(1)
        elif "Sending bootstrap to address" in line:
            result["action"] = action_messages["Sending bootstrap"]
            match = patterns["address"].search(line)
            if match:
                result["address"] = match.group(1)
        elif "Jumping to bootstrap" in line:
            result["action"] = action_messages["Jumping to bootstrap"]
            match = patterns["jumping"].search(line)
            if match:
                result["address"] = match.group(1)
                result["mode"] = match.group(2)

    return json.dumps(result, indent=4)

class Flash:
    def __init__(self, image, dry_run=False, daemon=False, verbose=False, queue=None, data_event=None):
        self.img = image
        self.daemon = daemon
        self.verbose = verbose
        self.queue = queue
        self.fastboot_sn = None
        self.data_event = data_event
        self.fastboot = None
        self.logger = logging.getLogger('aiot')
        if self.daemon:
            self.fastboot = aiot.Fastboot(dry_run=dry_run, daemon=daemon)
        else:
            self.fastboot = aiot.Fastboot(dry_run=dry_run)

    def flash_partition(self, partition, filename):
        def has_method(obj, method):
            return callable(getattr(obj, method, None))

        if has_method(self.img, 'generate_file'):
            self.img.generate_file(partition, filename)

        path = pathlib.Path(self.img.path) / filename

        def handle_output(json_output):
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set()  # notify flash_daemon

        if self.daemon:
            self.fastboot.flash(partition, str(path), handle_output)
        else:
            print(f"flashing {partition}={filename}")
            self.fastboot.flash(partition, str(path))

    def erase_partition(self, partition):
        if self.daemon:
            json_output = self.fastboot.erase(partition)
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set()  # notify flash_daemon
        else:
            print(f"erasing {partition}")
            self.fastboot.erase(partition)

    def flash_group(self, group):
        actions = self.img.groups[group]
        if self.daemon:
            while True:
                devices = self.fastboot.devices()
                if devices:
                    self.fastboot_sn = devices
                    break;

        if self.fastboot_sn:
            data = {
                "fastboot_sn": self.fastboot_sn,
            }
            json_output = json.dumps(data, indent=4)
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set()  # notify flash_daemon

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

        # handling reboot event
        if self.daemon:
            json_output = self.fastboot.reboot()
            if self.queue:
                self.queue.put(json_output)
                if self.data_event:
                    self.data_event.set() # notify flash_daemon
        else:
            self.fastboot.reboot()

    def flash_worker(self, image, args, queue=None, data_event=None):
        """Worker thread that performs the flashing."""
        if not self.check(args.targets):
            return

        if not args.dry_run:
            result = {
                "action": "",
                "error": "",
            }

            try:
                if platform.system() == 'Linux':
                    board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                              args.gpio_power, args.gpio_chip)
                elif platform.system() == 'Windows':
                    board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                                              args.gpio_power, None,
                                              serial=args.ftdi_serial)
                board.download_mode_boot()
            except RuntimeError as r:
                warning_str = "Unable to find and reset the board. Possible causes are:\n" \
                            "1. This is not a Genio 350/700 EVK, nor a Pumpkin board.\n" \
                            "2. The board port UART0 is not connected.\n" \
                            "3. The UART0 port is being opened by another tool, such as TeraTerm on Windows.\n" \
                            "You can now manually reset the board into DOWNLOAD mode.\n"
                if args.daemon:
                    if self.queue:
                        result["action"] = "Starting"
                        result["error"] = "Board Ctrl: Unable to find and reset the board. You can check detail with normal single download."
                        boardctl_json = json.dumps(result, indent=4)
                        self.queue.put(boardctl_json)
                        if self.data_event:
                            self.data_event.set()  # notify flash_daemon
                else:
                    logging.warning(r)
                    logging.warning(warning_str)
                    logging.info("Continue flashing...")
            except Exception as e:
                warning_str = "Board control failed. This might be caused by TTY/COM port being used by another process,\n" \
                            "such as TeraTerm or Putty on Windows. You could try manually put the board in DOWNLOAD mode. Continue flashing...\n"

                if args.daemon:
                    if self.queue:
                        result["action"] = "Starting"
                        result["error"] = "Board Ctrl: Board control failed. This might be caused by TTY/COM port being used by another process. You can check detail with --verbose."
                        boardctl_json = json.dumps(result, indent=4)
                        self.queue.put(boardctl_json)
                        if self.data_event:
                            self.data_event.set()  # notify flash_daemon
                else:
                    logging.warning(str(e))
                    logging.warning(warning_str)
                    logging.info("Continue flashing...")

        if not args.skip_bootstrap and not args.dry_run:
            # Capture the output of run_bootrom
            bootrom_output = run_bootrom(args)
            print(bootrom_output)
            # Parse the bootrom output
            bootrom_json = bootrom_log_parser(bootrom_output)

            if self.queue:
                self.queue.put(bootrom_json)
                if self.data_event:
                    self.data_event.set()  # notify flash_daemon

        self.flash(args.targets)

class GenioFlashWorker:
    def __init__(self, id, image=None, args=None):
        super().__init__()
        self.args = args
        self.id = id
        self.pid = None
        self.action = "Stopped"
        self.com_port = None
        self.fastboot_sn = None
        self.progress = None
        self.image = image
        self.start_time = None
        self.total_duration = None
        self.queue = Queue()
        self.data_event = Event()  # 使用 threading.Event
        self.logger = logging.getLogger('aiot')

    def start(self, args=None):
        # In-order not to create 2 download process with a worker, we keep start() here.
        pass

    def monitor(self):
        # We need to initialize the Flash class before calling `flash_worker` to avoid creating two instances in a single process.
        flasher = Flash(image=self.image, dry_run=self.args.dry_run, daemon=self.args.daemon, verbose=self.args.verbose, queue=self.queue, data_event=self.data_event)
        worker = threading.Thread(target=flasher.flash_worker, args=(self.image, self.args, self.queue, self.data_event))
        worker.start()
        monitor = threading.Thread(target=monitor_thread, args=(self, self.image, self.args, self.queue, self.data_event))
        monitor.start()