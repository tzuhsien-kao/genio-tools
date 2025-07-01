# SPDX-License-Identifier: MIT
# Copyright 2020 (c) BayLibre, SAS
# Author: Fabien Parent <fparent@baylibre.com>

import argparse
import logging
import sys
import textwrap

import aiot

class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        ret = super().emit(record)
        self.flush()
        return ret

class App: # pylint: disable=too-few-public-methods
    """ Common code for Genio tools"""

    def __init__(self, description="Genio tool"):
        self.logger = logging.getLogger('aiot')
        self.parser = argparse.ArgumentParser(
            description=textwrap.dedent(description),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.parser.add_argument('-v', '--verbose', action="store_true",
            help='Enable verbose output')
        self.parser.add_argument('-V', '--version', action="store_true",
            help='Show the version')

    def execute(self):
        args = self.parser.parse_args()

        if args.version:
            print(aiot.version)
            sys.exit(0)

        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.basicConfig(
                level=log_level,
                handlers=[FlushingStreamHandler()],
                force=True)

        return args
