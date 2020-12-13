# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

from pathlib import Path
from shutil import which
import platform
import os
import pwd
import grp

def print_check(description, status, instructions = None):
    if status:
        status_str = "\033[92mOK\033[0m"
    else:
        status_str = "\033[91mFAIL\033[0m"

    print(f"\033[1m{description}: {status_str}\033[0m")
    if not status and instructions:
        print(f"{instructions}")

class Config:
    UDEV_FILEPATH = '/etc/udev/rules.d/96-rity.rules'

    def title(self):
        return 'configure host environment'

    def check_udev_rules(self):
        mtk_rules = Path(Config.UDEV_FILEPATH)
        print_check('udev rules', mtk_rules.exists(),
            "In order for your host machine to be able to talk to the board "
            "through USB without needing root privileges, you need to create "
            "a udev rules that will grant the plugdev group access "
            "to your device:\n"
            """\t$ echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="201c", MODE="0660", GROUP="plugdev"\\nSUBSYSTEM=="usb", ATTR{idVendor}=="0403", MODE="0660", GROUP="plugdev"' | sudo tee -a """ + Config.UDEV_FILEPATH + "\n"
            "\t$ sudo udevadm control --reload-rules\n"
            "\t$ sudo udevadm trigger")

    def check_plugdev_grp(self):
        user = pwd.getpwuid(os.getuid())
        plugdev = grp.getgrnam('plugdev')
        print_check('plugdev group', user.pw_name in plugdev.gr_mem,
            "In order to be able to talk to the SoC, your user must be in "
            "the 'plugdev' group.\n"
            "Please run the following command to join "
            "the 'plugdev' group:\n"
            "\t$ sudo usermod -a -G plugdev $USER\n"
            "This command requires you to log out and log back in to your "
            "account to be in effect.")

    def check(self):
        print_check('fastboot', which('fastboot'),
            "fastboot is used to flash the board. Please install the android "
            "platform-tools for your platform:\n"
            "\thttps://developer.android.com/studio/releases/platform-tools")
        if platform.system() == 'Linux':
            self.check_udev_rules()
            self.check_plugdev_grp()
