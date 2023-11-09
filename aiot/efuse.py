import logging
import os
import re
import tempfile

import aiot

from aiot.bootrom import run_bootrom, add_bootstrap_group

app_description = """
    Genio efuse blowing tool

    This tool is used to blow efuse.
"""

def efuse_cfg_to_dict(fname):
    efuse = {}
    pat = re.compile('(\S+) *= *(\S+)')
    with open(fname) as f:
        efuse = {m.group(1):m.group(2) for m in pat.finditer(f.read())}
    return efuse

class EfuseTool(aiot.App):
    def __init__(self):
        aiot.App.__init__(self, description=app_description)
        self.setup_parser()
        self.logger = logging.getLogger('aiot')
        self.fastboot = aiot.Fastboot()

    def setup_parser(self):
        self.parser.add_argument('-y', action='store_true',
                help='Don\'t ask confirmation before blowing efuse')

        # Bootstrap
        add_bootstrap_group(self.parser)

        group = self.parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--blow', action='store_true',
                help='Blow the efuse using the efuse config file')
        group.add_argument('--read', action='store_true',
                help='Blow the efuse using the efuse config file')

        self.parser.add_argument('efuse_cfg',
                help='efuse config file, to be read or written to device')

    def execute(self):
        image = None
        chip = None

        args = super().execute()

        if not args.skip_bootstrap:
            run_bootrom(args)

        if args.blow:
            # Try to read efuse first to validate if we can read it and if
            # the fuse map is correct
            with tempfile.TemporaryDirectory() as tmpdirname:
                self.fastboot.fetch("efuse", str(tmpdirname + "/efuse.cfg"))
                if not self.precheck(args.efuse_cfg, str(tmpdirname + "/efuse.cfg")):
                    self.logger.error("Please check " + args.efuse_cfg)

            response = None
            if (not args.y):
                self.logger.warn(f"You are about to blow efuses which is not revertible")
                self.logger.warn(f"The following efuses will be blow")
                efuse_cfg_dict = efuse_cfg_to_dict(args.efuse_cfg)
                for efuse in efuse_cfg_dict:
                    value = efuse_cfg_dict[efuse]
                    if int(value, 16) != 0:
                        self.logger.warn("{}: {}".format(efuse, value))
                response = input("Type 'yes' to continue:")
            if response == "yes" or args.y:
                self.logger.info("blowing efuse ...")
                self.fastboot.flash("efuse", args.efuse_cfg)
                self.logger.info("checking efuse ...")
                with tempfile.TemporaryDirectory() as tmpdirname:
                    self.fastboot.fetch("efuse", str(tmpdirname + "/efuse.cfg"))
                    if self.check(args.efuse_cfg, str(tmpdirname + "/efuse.cfg")):
                        self.logger.info("efuse blow success")
                    else:
                        self.logger.error("Failed to write efuse")

        if args.read:
            self.fastboot.fetch("efuse", args.efuse_cfg)

    def check(self, efuse_cfg, efuse_read, precheck=False):
        efuse_cfg_dict = efuse_cfg_to_dict(efuse_cfg)
        efuse_read_dict = efuse_cfg_to_dict(efuse_read)

        res = 1
        for var in efuse_read_dict:
            if var not in efuse_cfg_dict:
                self.logger.error("trying to write an unsupported efuse: " + var)
                res = 0

            if precheck:
                continue

            value = efuse_cfg_dict[var]
            if efuse_cfg_dict[var] != efuse_read_dict[var] and int(value, 16):
                self.logger.error("Read {}={}\n\texpected {}={}".format(
                    var, efuse_read_dict[var], var, efuse_cfg_dict[var]))
                res = 0

        return res

    def precheck(self, efuse_cfg, efuse_read):
        return self.check(efuse_cfg, efuse_read, True)

def main():
    tool = EfuseTool()
    tool.execute()
