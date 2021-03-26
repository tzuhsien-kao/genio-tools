# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

from pathlib import Path
from shutil import which
import hashlib
import platform
import os
import pwd
import grp

def print_check(description, status, instructions=None, extra_info=""):
    if status:
        status_str = "\033[92mOK\033[0m"
    else:
        status_str = "\033[91mFAIL\033[0m"

    print(f"\033[1m{description}: {status_str}\033[0m {extra_info}")
    if not status and instructions:
        print(f"{instructions}")

class Config:
    UDEV_FILEPATH = '/etc/udev/rules.d/96-rity.rules'
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

        if mtk_rules.exists():
            with open(Config.UDEV_FILEPATH) as fp:
                rules_md5_real = hashlib.md5(str.encode(fp.read()))

        md5_match = rules_md5_real.hexdigest() == \
                        rules_md5_reference.hexdigest()

        print_check('udev rules', md5_match,
            "In order for your host machine to be able to talk to the board "
            "through USB without needing root privileges, you need to create "
            "a udev rules that will grant user access to your device:\n"
            "\t$ echo '" + Config.UDEV_RULES + "' | sudo tee " + Config.UDEV_FILEPATH + "\n"
            "\t$ sudo udevadm control --reload-rules\n"
            "\t$ sudo udevadm trigger", f"(md5: {rules_md5_real.hexdigest()})")

    def check(self):
        print_check('fastboot', which('fastboot'),
            "fastboot is used to flash the board. Please install the android "
            "platform-tools for your platform:\n"
            "\thttps://developer.android.com/studio/releases/platform-tools")
        if platform.system() == 'Linux':
            self.check_udev_rules()
