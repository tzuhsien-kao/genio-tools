# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import logging
import platform
import sys
import time
import aiot

app_description = f"""
    Genio board control version {aiot.version}

    This tool is used to control MediaTek Genio and Pumpkin boards thorugh
    the FTDI serial chip connected to UART0 on the board.

    WARNING: This tool cannot be used with all the boards. Please
    refer to the board documentation to check whether this tool
    can be used.

    To use this board, you need to connect to the port labeled as
    UART0 on the Genio or Pumpkin boards. It is usually a micro-USB port.
"""

if platform.system() == 'Windows':
    app_description += f"""
    Example Usage (Windows)
    -----------------------

    `genio-board list`
        shows the SERIAL of all the connected FTDI chips

    `genio-board -s SERIAL program-ftdi`
        must be called at least once to properly program the FTDI chip of the Genio/Pumpkin
        board to use the "reset", "download" and "power" commands.

        On some boards, you might have to change the GPIO configurations ("--gpio-reset" and others) according to board design.
        If there is only one FTDI chip connected, the "-s SERIAL" option could be omitted.

    `genio-board -s SERIAL program-ftdi --ftdi-serial NEW_SERIAL`
        can be used to update the SERIAL of a given FTDI chip.

    `genio-board -s SERIAL reset`
        would hard reset the Genio or Pumpkin board

    `genio-board -s SERIAL download`
        would hard reset the Genio or Pumpkin board and put it into download mode, for subsequent
        image flashing process.

    If there is only one FTDI chip connected, the "-s SERIAL" option could be omitted.
"""

def do_board_command(args):
    board = aiot.BoardControl(args.gpio_reset, args.gpio_download,
                              args.gpio_power, args.gpio_chip,
                              serial = args.serial)

    if args.command == 'reset':
        board.reset()
    elif args.command == 'download':
        board.download_mode_boot()
    elif args.command == 'power':
        board.power()

def main():
    app = aiot.App(description=app_description)
    parser = app.parser
    logger = app.logger

    parser.add_argument('-s', '--serial',
                        type=str,
                        default=None,
                        help="(Windows only) Specify which board to connect to using FTDI serial. You can get serial with 'aiot-board list'")

    subparsers = parser.add_subparsers(
        dest = 'command',
    )

    list_parser = subparsers.add_parser('list',
                                        help = "List the serial number in EEPROM of all connected FTDI chips."
    )

    ftdi_parser = subparsers.add_parser('program-ftdi',
                                        help = "Program the FTDI EEPROM, such as serial, product name, and configure the CBUS(GPIO) settings used by reset, download, and power commands."
    )
    ftdi_parser.add_argument('--ftdi-product-name', type=str, default='undefined', help="Currently no effect.")
    ftdi_parser.add_argument('--ftdi-serial', '--set-serial', type=str, default=None, help="Update the serial number in eeprom.")

    board_parsers = [
        ftdi_parser,
        subparsers.add_parser('reset', help = "Reset the board"),
        subparsers.add_parser('download', help = "Reset and put the board into download mode"),
        subparsers.add_parser('power', help="Power on the board"),
    ]

    for b in board_parsers:
        b.add_argument('-c', '--gpio-chip', type=int, help='GPIOChip device')
        b.add_argument('-r', '--gpio-reset', type=int, default=1,
            help='GPIO to use to reset the SoC')
        b.add_argument('-d', '--gpio-download', type=int, default=2,
            help='GPIO to use to put the SoC in download mode (KPCOL0 pin)')
        b.add_argument('-p', '--gpio-power', type=int, default=0,
            help='GPIO to use to power on the SoC')
        b.set_defaults(func=do_board_command)

    args = app.execute()

    if not args.command:
        logger.error("No command(list/program-ftdi/reset/download) speficied.")
        parser.print_usage()
        sys.exit(-1)
    
    try:
        if args.command == 'list':
            ftdi = aiot.FtdiControl(args.serial)
            ftdi.print_device_list()
        elif args.command == 'program-ftdi':
            ftdi = aiot.FtdiControl(args.serial)
            ftdi.program(args.ftdi_product_name, args.gpio_reset,
                         args.gpio_download, args.gpio_power,
                         new_serial = args.ftdi_serial)
        else:
            args.func(args)
        sys.exit(0)
    except Exception as e:
        logger.error(e, exc_info = args.verbose)
        sys.exit(-1)

if __name__ == '__main__':
    main()