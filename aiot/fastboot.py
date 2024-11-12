# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import subprocess
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
            subprocess.run(command, check=True)

    def devices(self):
        # List connected fastboot devices.
        if self.dry_run:
            return []

        process = subprocess.Popen([self.bin, "devices"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
        stdout, _ = process.communicate()
        devices = stdout.strip().split('\n')
        return [line.split()[0] for line in devices if 'fastboot' in line]

    def flash(self, partition, filename, callback=None, fastboot_sn=None):
        # Flash a partition with a specified file.
        if self.dry_run:
            return

        command = [self.bin]
        if fastboot_sn:
            command += ["-s", fastboot_sn]
        command += ["flash", partition, filename]

        if self.daemon:
            stdout = ''
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    stdout += output.strip() + "\n"
                    self.parser.parse_log(stdout)
                    json_output = self.parser.get_event_as_json()
                    if callback:
                        callback(json_output)

            remaining_output = process.communicate()[0].strip()
            stdout += remaining_output
            self.parser.parse_log(stdout)
            return self.parser.get_event_as_json()
        else:
            subprocess.run(command, check=True)

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

    def reboot(self):
        if self.dry_run:
            return

    def reboot(self, fastboot_sn=None):
        # Reboot the device.
        command = [self.bin]
        if fastboot_sn:
            command += ["-s", fastboot_sn]
        command += ["reboot"]
        return self._run_command(command)

    def write_rpmb_key(self):
        # Write the RPMB key.
        self._run_command([self.bin, "oem", "rpmb_key"])