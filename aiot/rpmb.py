import logging
import os
import tempfile

import aiot

from aiot.bootrom import run_bootrom, add_bootstrap_group

app_description = """
    Genio RPMB key provisioning tool

    This tool is used to write the RPMB key.
"""

class RPMBTool(aiot.App):
    def __init__(self):
        aiot.App.__init__(self, description=app_description)
        self.setup_parser()
        self.logger = logging.getLogger('aiot')
        self.fastboot = aiot.Fastboot()

    def setup_parser(self):
        # Bootstrap
        add_bootstrap_group(self.parser)

    def execute(self):
        image = None
        chip = None

        args = super().execute()

        if not args.skip_bootstrap:
            run_bootrom(args)

        self.fastboot.write_rpmb_key()

def main():
    tool = RPMBTool()
    tool.execute()
