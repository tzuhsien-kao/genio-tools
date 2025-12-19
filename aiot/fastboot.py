# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import json
import logging
import subprocess
import threading
import sys
import time
from fastboot_log_parser import FlashLogParser

class Fastboot:
    def __init__(self, dry_run=False, daemon=False):
        self.dry_run = dry_run
        self.daemon = daemon
        self.bin = 'fastboot'
        self.parser = FlashLogParser()

    def _run_command(self, command):
        # Helper method to run a fastboot command.
        if self.dry_run:
            return None

        if self.daemon:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            stdout, _ = process.communicate()
            self.parser.parse_log(stdout)
            return self.parser.get_event_as_json()
        else:
            try:
                p = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,  # merge STDERR into STDOUT
                        shell=False,               # we need cmd parsing
                        text=True,                 # decode stdout to string
                    )

                # Poll process STDOUT and print immediately
                while True:
                    output = p.stdout.readline().rstrip()
                    if output == '' and p.poll() is not None:
                        break
                    if output:
                        print(output, flush=True)

                retcode = p.poll()
                return retcode
            except KeyboardInterrupt:
                sys.exit(1)

    def devices(self):
        # List connected fastboot devices.
        if self.dry_run:
            return []

        # Wait while the OS enumerates new fastboot devices; this takes about 2 seconds.
        time.sleep(2)
        process = subprocess.Popen([self.bin, "devices"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
        stdout, _ = process.communicate()
        devices = stdout.strip().split('\n')
        return [line.split()[0] for line in devices if 'fastboot' in line]

    def flash(self, partition, filename, callback=None, fastboot_sn=None):
        # Flash a partition with a specified file.
        if self.dry_run:
            return

        logger = logging.getLogger('aiot')
        command = [self.bin]
        if fastboot_sn:
            command += ["-s", fastboot_sn]
        command += ["flash", partition, filename]

        if self.daemon:
            stdout = ''
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            last_output_time = time.time()
            timeout_sec = 30
            watchdog_started = False

            def watchdog_fn():
                nonlocal last_output_time
                while process.poll() is None:
                    if time.time() - last_output_time > timeout_sec:
                        logger.error(f"[Fastboot] No output from fastboot for {timeout_sec} seconds, triggering callback for timeout.")
                        if callback:
                            callback('{"action": "Error", "error": "fastboot no output timeout"}')
                        break

            def handle_fastboot_noresp_error(json_output):
                nonlocal last_output_time, watchdog_started
                import json
                json_obj = json.loads(json_output)
                if (
                    json_obj
                    and json_obj.get('action') == 'writing'
                    and json_obj.get('status') == 'OKAY'
                    and str(json_obj.get('partition', '')).startswith('mmc')
                ):
                    last_output_time = time.time()
                    if not watchdog_started:
                        watchdog_thread = threading.Thread(
                            target=watchdog_fn,
                            daemon=True
                        )
                        watchdog_thread.start()
                        watchdog_started = True

            # Thread to read process.stdout lines
            def reader_thread_fn():
                for output in iter(process.stdout.readline, ''):
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        line = output.strip() + "\n"
                        self.parser.parse_log(line)
                        json_output = self.parser.get_event_as_json()
                        if callback:
                            callback(json_output)
                        handle_fastboot_noresp_error(json_output)
                process.stdout.close()

            reader_thread = threading.Thread(
                target=reader_thread_fn,
                daemon=True
            )
            reader_thread.start()

            # Wait for process to finish and reader thread to complete
            process.wait()
            reader_thread.join()
        else:
            self._run_command(command)

    def fetch(self, partition, filename):
        # Fetch a partition to a specified file.
        print(f"Fetching {partition} to {filename}")
        self._run_command([self.bin, "fetch", partition, filename])

    def erase(self, partition, fastboot_sn=None):
        # Erase a specified partition.
        command = [self.bin]
        if fastboot_sn:
            command += ["-s", fastboot_sn]
        command += ["erase", partition]
        return self._run_command(command)

    def reboot(self, fastboot_sn=None):
        if self.dry_run:
            return

        # Reboot the device.
        command = [self.bin]
        if fastboot_sn:
            command += ["-s", fastboot_sn]
        command += ["reboot"]
        return self._run_command(command)

    def write_rpmb_key(self):
        # Write the RPMB key.
        self._run_command([self.bin, "oem", "rpmb_key"])