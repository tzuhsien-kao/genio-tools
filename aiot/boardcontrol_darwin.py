# Copyright 2026 (c) MediaTek Inc.

import time
import logging

try:
    from pyftdi.ftdi import Ftdi
    from pyftdi.usbtools import UsbTools
    _CBUS_CONTROLLER_AVAILABLE = True
    try:
        from pyftdi.gpio import CbusGpioController
    except ImportError:
        # Older pyftdi versions expose it under a different path
        from pyftdi.ftdi import Ftdi as CbusGpioController # will fail gracefully below
        _CBUS_CONTROLLER_AVAILABLE = False
except ImportError:
    Ftdi = None
    CbusGpioController = None
    _CBUS_CONTROLLER_AVAILABLE = False

logger = logging.getLogger('aiot')

class BoardControl:
    """
    Board control for macOS Darwin using pylibftdi (libusb backend).

    Requires:
        brew install libusb
        pip install pyftdi
    """

    def __init__(self, gpio_reset=1, gpio_download=2, gpio_power=0,
                 gpio_chip=None, serial=None):
        if not _CBUS_CONTROLLER_AVAILABLE or CbusGpioController is None:
            raise RuntimeError(
                "pyftdi is not installed or is too old to provide CbusGpioController. \n"
                "Install/upgrade it with: pip install --upgrade pyftdi\n"
                "Also ensure libusb is installed: brew install libusb"
            )

        self.gpio_reset    = gpio_reset
        self.gpio_download = gpio_download
        self.gpio_power    = gpio_power
        self.serial        = serial

        # CBUS pins are addressed as a 4-bit nibble (CBUS0..CBUS3).
        self._mask_power    = 1 << gpio_power
        self._mask_reset    = 1 << gpio_reset
        self._mask_download = 1 << gpio_download
        self._all_outputs = (self._mask_power | self._mask_reset | self._mask_download)


        try:
            self._gpio = CbusGpioController()
            url = self._build_url(serial)
            # direction mask: 1 = output for each of our three pins
            self._gpio.configure(url, direction=self._all_outputs)
            # Start with all pins de-asserted (high/ inactive)
            self._gpio_write(self._all_outputs)
            logger.debug(
                "BoardControl (Darwin): opened FTDI device url=%s "
                "direction=0x%02X", url, self._all_outputs
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to open FTDI device on macOS: {e}\n"
                "Ensure libusb is installed (brew install libusb) "
                ", the FTDI device is connected, and its CBUS pins have "
                "been configured as GPIO via aiot-board program-ftdi."
            ) from e

    @staticmethod
    def _build_url(serial):
        """ Build a pyftdi device URL, optionally filtered by serial number."""
        if serial:
            return f'ftdi://ftdi:232r:{serial}/1'
        return 'ftdi://ftdi:232r/1'

    # ------------------------------------------------------------------
    # Low-level CBUS pin helpers
    # ------------------------------------------------------------------

    def _set_pin(self, pin_mask, high: bool):
        """Set a single pin high or low without disturbing other pins."""
        current = self._gpio.read()
        if high:
            self._gpio.write(current | mask)
        else:
            self._gpio.write(current & ~mask)

    # ------------------------------------------------------------------
    # Public interface (mirrors boardcontrol_linux / boardcontrol_win)
    # ------------------------------------------------------------------

    def download_mode_boot(self):
        """
        Reset the board into USB download mode (BootROM mode).

        Sequence (matches Linux/Windows board control):
          1. Assert RESET (hold low)
          2. Assert DOWNLOAD pin  (KPCOL0 high)
          3. Power cycle or pulse power
          4. Deassert RESET  → SoC boots into BootROM/download mode
          5. Deassert DOWNLOAD pin after a short delay
        """
        logger.info("BoardControl (Darwin): entering download mode")

        # Assert DOWNLOAD, then pulse reset while power is kept on
        # same sequence as boardcontrol_win
        self._set_pin(self._mask_download, True)
        self._set_pin(self._mask_reset, False)
        time.sleep(0.1)
        self._set_pin(self._mask_reset, True)
        time.sleep(0.5)
        self._set_pin(self._mask_download, False)
        logger.info("BoardControl (Darwin): download mode sequence complete")

    def reset(self):
        """Hard-reset the board into normal boot mode."""
        logger.info("BoardControl (Darwin): reset")
        self._set_pin(self._mask_download, False)
        self._set_pin(self._mask_reset, False)
        time.sleep(0.1)
        self._set_pin(self._mask_reset, True)
        logger.info("BoardControl (Darwin): reset complete")

    # Alias used by board.py
    normal_boot = reset

    def close(self):
        """Release the FTDI device."""
        try:
            self.i_gpio.close()
        except Exception:
            pass
