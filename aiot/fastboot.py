# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import subprocess

class Fastboot:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.bin = 'fastboot'

        if self.dry_run:
            return

    def flash(self, partition, filename):
        print(f"flashing {partition}={filename}")

        if self.dry_run:
            return

        subprocess.run([self.bin, "flash", partition, filename], check=True)

    def fetch(self, partition, filename):
        print(f"fetching {partition}={filename}")

        if self.dry_run:
            return

        subprocess.run([self.bin, "fetch", partition, filename], check=True)

    def erase(self, partition):
        print(f"erasing {partition}")

        if self.dry_run:
            return

        subprocess.run([self.bin, "erase", partition], check=True)

    def reboot(self):
        if self.dry_run:
            return

        subprocess.run([self.bin, "reboot"], check=True)

    def write_rpmb_key(self):
        if self.dry_run:
            return

        subprocess.run([self.bin, "oem", "rpmb_key"], check=True)
