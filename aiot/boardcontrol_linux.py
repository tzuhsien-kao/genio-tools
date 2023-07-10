# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import gpiod
import sys
import time

class BoardControl:
    GPIO_LOW = 0
    GPIO_HIGH = 1

    def __init__(self, reset_gpio, dl_gpio, pwr_gpio, chip_id = None, serial = None):
        chip = self.get_gpiochip(chip_id)

        config = gpiod.line_request()
        config.consumer = "aiot-board"
        config.request_type = gpiod.line_request.DIRECTION_OUTPUT

        self.reset_gpio = chip.get_line(reset_gpio)
        self.dl_gpio = chip.get_line(dl_gpio)
        self.pwr_gpio = chip.get_line(pwr_gpio)

        self.reset_gpio.request(config)
        self.dl_gpio.request(config)
        self.pwr_gpio.request(config)

        self.logger = logging.getLogger('aiot')

    def get_gpiochip(self, chip_id = None):
        known_devices = []
        logger = logging.getLogger('aiot')

        if chip_id is not None:
            return gpiod.chip(chip_id)

        for chip in gpiod.chip_iter():
            if chip.label == 'ftdi-cbus':
                known_devices.append(chip)

        if len(known_devices) == 0:
            raise RuntimeError("No 'ftdi-cbus' device found")

        if len(known_devices) > 1:
            raise RuntimeError("Several 'ftdi-cbus' device found")

        return known_devices[0]

    def _set_gpio(self, gpio, value):
        try:
            gpio.set_value(value)
        except PermissionError:
            self.logger.error("FTDI chip not configured")

    def reset(self):
        self.reset_gpio.set_value(BoardControl.GPIO_HIGH)
        self.reset_gpio.set_value(BoardControl.GPIO_LOW)

    def download_mode_boot(self):
        self.dl_gpio.set_value(BoardControl.GPIO_HIGH)
        self.reset()
        self.dl_gpio.set_value(BoardControl.GPIO_LOW)

    def power(self):
        self.pwr_gpio.set_value(BoardControl.GPIO_HIGH)
        time.sleep(1)
        self.pwr_gpio.set_value(BoardControl.GPIO_LOW)


