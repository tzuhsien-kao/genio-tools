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
        self.fastboot_sn = None
        self.parser = FlashLogParser()

        if self.dry_run:
            return

    def devices(self):
        if self.dry_run:
            return
        process = subprocess.Popen([self.bin, "devices"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
        stdout, _ = process.communicate()
        devices = stdout.strip().split('\n')
        fastboot_sn = [line.split()[0] for line in devices if 'fastboot' in line]
        self.fastboot_sn = ''.join(fastboot_sn)
        return self.fastboot_sn

    def flash(self, partition, filename, callback=None):
        if self.dry_run:
            return

        if self.daemon:
            stdout = ''
            if self.fastboot_sn:
                process = subprocess.Popen([self.bin, "-s", self.fastboot_sn, "flash", partition, filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            else:
                process = subprocess.Popen([self.bin, "flash", partition, filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Process each line of output, such as printing or other operations
                    stdout += output.strip() + "\n"

                    self.parser.parse_log(stdout)
                    json_output = self.parser.get_event_as_json()
                    if callback:
                        callback(json_output)  # Pass the output to a specific callback function.

            remaining_output = process.communicate()[0].strip()
            stdout += remaining_output
            self.parser.parse_log(stdout)
            json_output = self.parser.get_event_as_json()
            return json_output
        else:
            subprocess.run([self.bin, "flash", partition, filename], check=True)

    def fetch(self, partition, filename):
        print(f"fetching {partition}={filename}")

        if self.dry_run:
            return

        subprocess.run([self.bin, "fetch", partition, filename], check=True)

    def erase(self, partition):
        if self.dry_run:
            return

        if self.daemon:
            if self.fastboot_sn:
                process = subprocess.Popen([self.bin, "-s", self.fastboot_sn, "erase", partition], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            else:
                process = subprocess.Popen([self.bin, "erase", partition], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)

            stdout, _ = process.communicate()
            self.parser.parse_log(stdout)
            json_output = self.parser.get_event_as_json()
            return json_output
        else:
            subprocess.run([self.bin, "erase", partition], check=True)

    def continve(self):
        if self.dry_run:
            return
        subprocess.run([self.bin, "continue"], check=True)

    def reboot(self):
        if self.dry_run:
            return

        if self.daemon:
            if self.fastboot_sn:
                process = subprocess.Popen([self.bin, "-s", self.fastboot_sn, "reboot"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            else:
                process = subprocess.Popen([self.bin, "reboot"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)

            stdout, _ = process.communicate()
            self.parser.parse_log(stdout)
            json_output = self.parser.get_event_as_json()
            return json_output
        else:
            subprocess.run([self.bin, "reboot"], check=True)

    def write_rpmb_key(self):
        if self.dry_run:
            return

        subprocess.run([self.bin, "oem", "rpmb_key"], check=True)
