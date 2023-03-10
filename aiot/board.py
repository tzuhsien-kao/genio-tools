# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import platform
import sys
import time
import aiot

app_description = """
    AIoT board control

    This tool is used to control MediaTek boards.

    WARNING: This tool cannot be used with all the boards. Please
    refer to the board documentation to check whether this tool
    can be used.
"""

def main():
    app = aiot.App(description=app_description)
    parser = app.parser
    logger = app.logger

    parser.add_argument('command', type=str,
        choices=['reset', 'download', 'power', 'program-ftdi'])
    parser.add_argument('-c', '--gpio-chip', type=int, help='GPIOChip device')
    parser.add_argument('-r', '--gpio-reset', type=int, default=1,
        help='GPIO to use to reset the SoC')
    parser.add_argument('-d', '--gpio-download', type=int, default=2,
        help='GPIO to use to put the SoC in download mode (KPCOL0 pin)')
    parser.add_argument('-p', '--gpio-power', type=int, default=0,
        help='GPIO to use to power on the SoC')
    parser.add_argument('--ftdi-product-name', type=str, default='undefined')

    args = app.execute()

    if args.command == 'program-ftdi':
        ftdi = aiot.FtdiControl()
        try:
            ftdi.program(args.ftdi_product_name, args.gpio_reset,
                         args.gpio_download, args.gpio_power)
        except Exception as e:
            logger.error(e)
            sys.exit(-1)
        sys.exit(0)

    board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                              args.gpio_power, args.gpio_chip)

    if args.command == 'reset':
        board.reset()
    elif args.command == 'download':
        board.download_mode_boot()
    elif args.command == 'power':
        board.power()


if __name__ == '__main__':
    main()