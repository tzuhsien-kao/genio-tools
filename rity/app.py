# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import argparse
import logging
import sys
import textwrap

import rity

class App: # pylint: disable=too-few-public-methods
    """ Common code for RITY tools"""

    def __init__(self, description="RITY tool"):
        self.logger = logging.getLogger('rity')
        self.parser = argparse.ArgumentParser(
            description=textwrap.dedent(description),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.parser.add_argument('-v', '--verbose', action="store_true",
            help='Enable verbose output')
        self.parser.add_argument('-V', '--version', action="store_true",
            help='Show the version')

        logging.basicConfig(level=logging.INFO)

    def execute(self):
        args = self.parser.parse_args()

        if args.version:
            print(rity.version)
            sys.exit(0)

        if args.verbose:
            logging.basicConfig(level=logging.DEBUG)

        return args
