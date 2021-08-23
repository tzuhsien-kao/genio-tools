# SPDX-License-Identifier: MIT
# Copyright 2020 BayLibre, SAS.
# Author: Fabien Parent <fparent@baylibre.com>

import platform

from aiot.app import App
from aiot.config import Config
from aiot.fastboot import Fastboot
from aiot.flash import Flash
from aiot.ubootenv import UBootEnv
from aiot.version import version

if platform.system() == 'Linux':
    from aiot.board import BoardControl
    from aiot.ftdi import FtdiControl
