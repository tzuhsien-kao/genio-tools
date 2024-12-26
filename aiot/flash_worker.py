# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import json
import logging
import threading
from queue import SimpleQueue

import aiot
from aiot.bootrom_log_parser import parse_log_line, bootrom_log_parser

class GenioFlashWorker(threading.Thread):
    def __init__(self, id, image=None, args=None, daemon=None):
        super().__init__()
        self.args = args
        self.id = id
        self.action = "Stopped"
        self.com_port = None
        self.progress = None
        self.image = image
        self.queue = SimpleQueue()
        self.data_event = threading.Event()  # use threading.Event
        self.logger = logging.getLogger('aiot')
        self.flasher = None
        self.daemon = daemon
        self.first_erasing = True

        # Dictionary to store shared properties with daemon
        self.shared_properties = {
            "fastboot_sn": None,
            "start_time": None,
            "total_duration": None
        }

    def run(self):
        from aiot.flash import Flash
        # Start the flasher thread
        self.flasher = Flash(image=self.image, dry_run=self.args.dry_run, daemon=self.daemon, verbose=self.args.verbose, queue=self.queue, data_event=self.data_event)
        flasher_thread = threading.Thread(target=self.flasher.flash_worker, args=(self.image, self.args, self.queue, self.data_event))
        flasher_thread.start()

        # Monitor thread logic
        try:
            while True:
                self.data_event.wait()

                while not self.queue.empty():
                    json_input = self.queue.get(timeout=2)
                    data = json.loads(json_input)

                    # Update fastboot_sn if it's a valid string
                    if isinstance(self.flasher.fastboot_sn, str) and self.flasher.fastboot_sn:
                        self.shared_properties["fastboot_sn"] = self.flasher.fastboot_sn

                    # Update worker's attributes
                    for key in ["action", "com_port", "progress", "partition", "error"]:
                        if key in data:
                            setattr(self, key, data[key])

                    # Log based on action and error
                    log_message = self.format_log_message(data)
                    self.log_based_on_action(log_message, data)

                self.data_event.clear()

        except json.JSONDecodeError:
            self.handle_json_decode_error()
        except Exception as e:
            self.handle_general_error(e)

    def format_log_message(self, data):
        # Format the log message for the worker based on its attributes and data.
        data_str = ', '.join(f'{key}: "{value}"' if key == 'error' else f'{key}: {value}' for key, value in data.items())
        log_prefix = f"Worker {self.id}, " if self.args.verbose else f"Worker {self.id}, "
        return f"{log_prefix}{self.com_port}, {self.shared_properties['fastboot_sn']}, {{{data_str}}}"

    def log_based_on_action(self, log_message, data):
        # Log messages based on the current action of the worker.
        if self.action in ["Starting", "Jumping DA", "rebooting", "done"]:
            self.logger.info(log_message)
        elif not self.args.verbose and self.action == "erasing" and self.first_erasing:
            self.logger.info(f"{log_message} flashing...")
            self.first_erasing = False
        elif 'error' in data:
            self.logger.warning(log_message)
        else:
            self.logger.debug(log_message)

    def handle_json_decode_error(self):
        # Handle JSON decoding errors by setting the worker's action to 'Error'.
        self.action = "Error"
        self.logger.error("Failed to decode JSON output")

    def handle_general_error(self, error):
        # Handle general errors by logging the error message.
        self.action = "Error"
        self.logger.error(str(error))