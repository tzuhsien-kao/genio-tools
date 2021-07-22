# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import pyftdi.eeprom
import usb

class FtdiControl:
    def __init__(self):
        self.logger = logging.getLogger('rity')

    def find_device(self):
        dev = list(usb.core.find(find_all=True, idVendor=0x0403))
        if len(dev) == 0:
            raise RuntimeError("Cannot find any FTDI device")
        elif len(dev) > 1:
            raise RuntimeError("More than one FTDI device connected")

        return dev[0]

    def program(self, product_name, reset_gpio, download_gpio, power_gpio):
        device = self.find_device()

        eeprom = pyftdi.eeprom.FtdiEeprom()
        eeprom.open(device)

        # HACKS for bad FTDI-232R devices
        if eeprom._eeprom[0x07] == 0x00 and device.idProduct == 0x6001:
            self.logger.warning("Bad FTDI type. Assuming FTDI-232R device.")
            eeprom._eeprom[0x06] = 0x00
            eeprom._eeprom[0x07] = 0x06
            eeprom._decode_eeprom()

        eeprom.set_property(f"cbus_func_{power_gpio}", "GPIO")
        eeprom.set_property(f"cbus_func_{reset_gpio}", "GPIO")
        eeprom.set_property(f"cbus_func_{download_gpio}", "GPIO")

        eeprom.commit(dry_run = False)
        eeprom.reset_device()

        self.logger.info("FTDI device programmed successfully")
