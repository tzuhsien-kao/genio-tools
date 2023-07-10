# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import pyftdi.eeprom
import usb

class FtdiControl:
    def __init__(self, serial = None):
        self.logger = logging.getLogger('aiot')
        self.serial = serial

    def print_device_list(self):
        pyftdi.ftdi.Ftdi.show_devices()

    def find_device(self, serial = None):
        if serial:
            for usb_dev, dev_idx in pyftdi.ftdi.Ftdi.list_devices():
                if serial == usb_dev.sn:
                    self.logger.debug(f"Matching serial found:{usb_dev}")
                    return pyftdi.usbtools.UsbTools.get_device(usb_dev)
            self.logger.error(f"Cannot find FTDI device with serial={serial}")
            return None
        else:
            return self._find_device_by_usb()

    def _find_device_by_usb(self):
        dev = list(usb.core.find(find_all=True, idVendor=0x0403))
        if len(dev) == 0:
            raise RuntimeError("Cannot find any FTDI device")
        elif len(dev) > 1:
            raise RuntimeError("More than one FTDI device connected")

        return dev[0]

    def program(self, product_name, reset_gpio, download_gpio, power_gpio, new_serial = None):
        device = self.find_device(self.serial)

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

        if new_serial:
            # Currently Linux version does not support serial setting.
            # If we set serial, the following error occurs:
            # pyftdi.ftdi.FtdiError: EEPROM does not support mirroring
            # eeprom.set_serial_number(new_serial)
            self.logger.error("Setting FTDI serial number is not supported")

        eeprom.commit(dry_run = False)
        eeprom.reset_device()

        self.logger.info("FTDI device programmed successfully")
