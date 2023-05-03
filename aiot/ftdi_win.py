# SPDX-License-Identifier: MIT
# Copyright 2023 (c) MediaTek, Inc.
# Author: Pablo Sun <pablo.sun@mediatek.com>
#
# ftd2xx is Windows-only wrapper over FTDI's DLL
# https://pypi.org/project/ftd2xx/
#
# You need to install d2xx drivers on Windows:
# https://ftdichip.com/drivers/d2xx-drivers/
#
# Using this DLL wrapper allows us to remove dependencies
# to libusb and libgpiod, which requires additional
# installation on Windows.
#
# Reference: https://iosoft.blog/2018/12/02/ftdi-python-part-1/
#
# As an alternative, you could also use the utility FT_PROG
# to program the FTDI eeprom:
# https://www.ftdichip.com/old2020/Support/Utilities.htm#FT_PROG

import logging
import time
import ftd2xx as ftd
from enum import IntEnum

class FT232R_CBUS_OPTIONS(IntEnum):
    '''
    FT232R CBUS EEPROM OPTIONS - Ignored for FT245R
    '''
    FT_232R_CBUS_TXDEN = 0x00 
    FT_232R_CBUS_PWRON = 0x01 
    FT_232R_CBUS_RXLED = 0x02 
    FT_232R_CBUS_TXLED = 0x03
    FT_232R_CBUS_TXRXLED = 0x04 
    FT_232R_CBUS_SLEEP = 0x05 
    FT_232R_CBUS_CLK48 = 0x06 
    FT_232R_CBUS_CLK24 = 0x07 
    FT_232R_CBUS_CLK12 = 0x08 
    FT_232R_CBUS_CLK6 = 0x09 
    FT_232R_CBUS_IOMODE = 0x0A 
    FT_232R_CBUS_BITBANG_WR = 0x0B
    FT_232R_CBUS_BITBANG_RD = 0x0C

def get_model(t):
    return ftd.defines.Device(t).name

class FtdiControl:
    def __init__(self, serial = None):
        self.logger = logging.getLogger('aiot')
        self.logger.debug(f"FTDI D2xx library version: {ftd.getLibraryVersion()}")
        self.serial = serial
    
    def print_device_list(self):
        ftd.createDeviceInfoList()
        devices = ftd.listDevices()
        if not devices:
            self.logger.info("No FTDI chips connected")
            return

        for serial in devices:
            if serial == b'':
                print("<occupied>")
            else:
                print(str(serial, 'utf-8'))

    def find_device(self, serial = None):
        if serial:
            d = ftd.openEx(serial.encode('utf-8'))
            if not d:
                raise RuntimeError(f"Cannot find assigned FTDI device {serial}")
        else:
            devices = ftd.listDevices()
            if not devices:
                raise RuntimeError("Cannot find any FTDI device")
            elif len(devices) > 1:
                raise RuntimeError("More than one FTDI device connected. Assign device by serial with option '-s SERIAL'.")
            d = ftd.open(0)
               
        com = d.getComPortNumber()
        info = d.getDeviceInfo()
        self.logger.info(f"Found FTDI device {get_model(d.type)} in COM{com}: {info}")
        if d.type != ftd.defines.Device.FT_232R:
            raise RuntimeError("Only FT232R is supported for now")
        return d
    
    def config_cbus_iomode(self, eeprom, bus_pin):
        setattr(eeprom, f'Cbus{bus_pin}', FT232R_CBUS_OPTIONS.FT_232R_CBUS_IOMODE)

    def program(self, product_name, reset_gpio, download_gpio, power_gpio, new_serial = None):
        device = self.find_device(self.serial)

        eeprom = device.eeRead()

        # HighDrive IO is required to drive Genio 350 EVK reset pin
        eeprom.HighDriveIOs = 1

        if new_serial:
            eeprom.SerialNumber = new_serial.encode('utf-8')

        for pin in (reset_gpio, download_gpio, power_gpio):
            self.config_cbus_iomode(eeprom, pin)
        
        device.eeProgram(eeprom)
        # reset & cycle port is required for 
        # FTD driver to update the new serial number
        device.resetDevice()
        device.cyclePort()
        device.close()
        self.logger.info("FTDI device programmed successfully, resetting device...")
        time.sleep(3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    c = FtdiControl()
    c.print_device_list()
    #c.find_device().close()
    #c.program("", 1, 2, 0)