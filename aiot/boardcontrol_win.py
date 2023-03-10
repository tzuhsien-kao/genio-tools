# SPDX-License-Identifier: MIT
# Copyright 2023 (c) MediaTek, Inc
# Author: Pablo Sun <pablo.sun@mediatek.com>

import logging
import sys
import time
from aiot.ftdi_win import FtdiControl as FtdiControl

class BoardControl:
    GPIO_LOW = 0
    GPIO_HIGH = 1

    def __init__(self, reset_gpio, dl_gpio, pwr_gpio, chip_id = None):
        self.logger = logging.getLogger('aiot')
        self.rst_gpio = reset_gpio
        self.dl_gpio = dl_gpio
        self.pwr_gpio = pwr_gpio

        self._init_cbus()

    def _init_cbus(self, chip_id = None):
        '''
        Excerpt from AN232R-01_FT232RBitBangModes.pdf
        section 1.4 CBUS Bit Bang Mode:

        FT_SetBitMode also provides the means to write data to the CBUS pins.
        The upper nibble of the Mask parameter controls which pins are inputs or
        outputs, while the lower nibble controls which of the outputs are high or low.  
        '''
        ftdi = FtdiControl()
        self.dev = ftdi.find_device()
        return 0

    def mask_high(self):
        '''
        The high nimble are the pins that should be OUTPUT
        '''
        mask = 0x0
        for b in (self.rst_gpio, self.dl_gpio, self.pwr_gpio):
            mask |= 0x1 << (4 + b) 
        return mask

    def _set_gpio(self, rst, dl):
        mask = self.mask_high() | (rst << self.rst_gpio) | (dl << self.dl_gpio)
        self.dev.setBitMode(mask, 0x20)

    def reset(self):
        '''
        reboot and restore to board to NORMAL mode
        '''
        self.logger.debug("reset pull high")
        self._set_gpio(rst = 1, dl = 0)
        time.sleep(0.1)
        self._set_gpio(rst = 0, dl = 0)
        self.logger.debug("reset pull low")
        self.dev.close()

    def download_mode_boot(self):
        '''
        reboot and set the board to DOWNLOAD mode
        '''
        self._set_gpio(rst = 0, dl = 1)
        time.sleep(0.1)
        self._set_gpio(rst = 1, dl = 1)
        time.sleep(0.1)
        self._set_gpio(rst = 0, dl = 1)
        # we need to release FTDI device
        # note that the DL pin state remains HIGH
        # even if we close this device.
        self.dev.close()

    def power(self):
        raise RuntimeError("power is not supported now")


if __name__ == "__main__":
    b = BoardControl(1, 2, 0)
    b.reset()
    # b.download_mode_boot()