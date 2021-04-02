# SPDX-License-Identifier: MIT
# Copyright 2020 BayLibre, SAS.
# Author: Fabien Parent <fparent@baylibre.com>

import platform

from rity.app import App
from rity.board import BoardControl
from rity.config import Config
from rity.fastboot import Fastboot
from rity.flash import Flash
from rity.ubootenv import UBootEnv
from rity.version import version

if platform.system() == 'Linux':
    from rity.board import BoardControl
    from rity.ftdi import FtdiControl
