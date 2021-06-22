# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

from pathlib import Path
from shutil import which
import hashlib
import platform

import rity

def print_check(description, status, instructions=None, extra_info=""):
    if status:
        status_str = "OK"
        if platform.system() != "Windows":
            status_str = f"\033[92m{status_str}\033[0m"
    else:
        status_str = "FAIL"
        if platform.system() != "Windows":
            status_str = f"\033[91m{status_str}\033[0m"

    info = f"{description}: {status_str}"
    if platform.system() != "Windows":
        info = f"\033[1m{info}\033[0m"
    print(f"{info} {extra_info}")
    if not status and instructions:
        print(f"{instructions}")

class Config:
    UDEV_FILEPATH = '/etc/udev/rules.d/72-rity.rules'
    UDEV_RULES = """
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="201c", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="gpio", MODE="0660", TAG+="uaccess"
""".lstrip()

    def title(self):
        return 'configure host environment'

    def check_udev_rules(self):
        mtk_rules = Path(Config.UDEV_FILEPATH)
        rules_md5_reference = hashlib.md5(str.encode(Config.UDEV_RULES))
        rules_md5_real = None
        rules_md5 = None
        md5_match = False

        if mtk_rules.exists():
            with open(Config.UDEV_FILEPATH) as fp:
                rules_md5_real = hashlib.md5(str.encode(fp.read()))

            rules_md5 = rules_md5_real.hexdigest()

        md5_match = rules_md5 == rules_md5_reference.hexdigest()

        print_check('udev rules', md5_match,
            "In order for your host machine to be able to talk to the board "
            "through USB without needing root privileges, you need to create "
            "a udev rules that will grant user access to your device:\n"
            "\t$ echo -n '" + Config.UDEV_RULES + "' | sudo tee " + Config.UDEV_FILEPATH + "\n"
            "\t$ sudo udevadm control --reload-rules\n"
            "\t$ sudo udevadm trigger", f"(md5: {rules_md5})")

    def check(self):
        print_check('fastboot', which('fastboot'),
            "fastboot is used to flash the board. Please install the android "
            "platform-tools for your platform:\n"
            "\thttps://developer.android.com/studio/releases/platform-tools")
        if platform.system() == 'Linux':
            self.check_udev_rules()

app_description = """
    RITY configuration tool

    This tool is used to check the environment of the host machine.
"""

def main():
    app = rity.App(description=app_description)
    app.execute()

    config = rity.Config()
    config.check()
