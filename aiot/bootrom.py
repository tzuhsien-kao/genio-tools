# SPDX-License-Identifier: MIT

import logging
import platform
import re
import subprocess
import aiot_bootrom.bootrom
from pathlib import Path

logger = logging.getLogger('aiot')

# Default bootstrap binary names to auto-detect, in priority order.
# Entries are treated as regular expressions matched against file names,
# so 'mt.+-da.bin' matches boards like 'mt8365-da.bin' or 'mt8390-da.bin'.
DEFAULT_BOOTSTRAP_NAMES = ['lk.bin', 'da.bin', r'mt.+-da\.bin']

# ── platform-specific USB wait ──
if platform.system() == 'Linux':
    import pyudev

    def create_udev_monitor():
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context, source='kernel')
        monitor.filter_by(subsystem="usb")
        monitor.start()
        return monitor

    def _is_bootrom_event(action, device):
        if action != 'add' or device.get('DEVTYPE') != 'usb_device':
            return False

        try:
            vendor = device.attributes.asstring('idVendor')
            product = device.attributes.asstring('idProduct')
        except (AttributeError, KeyError, OSError):
            return False

        return vendor.lower() == '0e8d' and product.lower() == '0003'

    def udev_wait(monitor=None):
        if monitor is None:
            monitor = create_udev_monitor()
        for action, device in monitor:
            if _is_bootrom_event(action, device):
                break

def find_bootstrap(image_path):
    # Search image_path for a default bootstrap binary, returning the name of
    # the first match in DEFAULT_BOOTSTRAP_NAMES priority order, or None.
    image_path = Path(image_path)
    if not image_path.is_dir():
        return None
    entries = sorted(entry.name for entry in image_path.iterdir() if entry.is_file())
    for pattern in DEFAULT_BOOTSTRAP_NAMES:
        regex = re.compile(pattern)
        for name in entries:
            if regex.fullmatch(name):
                return name
    return None

# ── argument parser ──
def add_bootstrap_group(parser):
    group = parser.add_argument_group('Bootstrap')
    group.add_argument('-P', '--path', type=str, help='Path to image',
        default=".")
    group.add_argument('--skip-bootstrap', action="store_true",
        help="Don't bootstrap the board")
    group.add_argument('--bootstrap', type=str, default=None,
        metavar='lk.bin',
        help='bootstrap binary used for flashing '
             '(default: auto-detect lk.bin, da.bin, or mt*-da.bin)')
    group.add_argument('--bootstrap-sign', type=str, default='lk.sign',
        metavar='lk.sign',
        help='bootstrap binary signature used for flashing with DAA enabled '
             '(default: lk.sign)')
    group.add_argument('--bootstrap-auth', type=str, default='auth_sv5.auth',
        metavar='auth_sv5.auth',
        help='authentication file used for flashing with DAA enabled '
             '(default: auth_sv5.auth)')
    group.add_argument('--daa', action="store_true",
        help="flash with DAA enabled")
    group.add_argument('--bootstrap-addr', type=int, default=0x0,
        metavar='0x0',
        help='Address where the bootstrap binary will be loaded '
             '(default: 0x0)')
    group.add_argument('--bootstrap-mode', type=str, default='aarch64',
                       choices=['aarch64', 'aarch32'])

# ── bootrom runner ──
def run_bootrom(args, udev_monitor=None):
    image_path = Path(args.path)

    bootstrap = args.bootstrap
    if bootstrap is None:
        bootstrap = find_bootstrap(image_path)
        if bootstrap is None:
            names = ', '.join(DEFAULT_BOOTSTRAP_NAMES)
            raise FileNotFoundError(
                f"No bootstrap binary found in '{image_path}' "
                f"(searched for: {names}). "
                f"Use --bootstrap to specify one manually.")
    elif not (image_path / bootstrap).is_file():
        raise FileNotFoundError(
            f"Bootstrap binary '{image_path / bootstrap}' does not exist.")

    logger.info(f"Using bootstrap binary: {bootstrap}")

    bootrom_app = [
        'aiot-bootrom',
        '--bootstrap', image_path / bootstrap,
        '--bootstrap-addr', hex(args.bootstrap_addr),
        '--bootstrap-mode', args.bootstrap_mode,
    ]

    if args.daa:
        bootrom_app.extend([
            '-s', image_path / args.bootstrap_sign,
            '-t', image_path / args.bootstrap_auth,
        ])
    else:
        # By default, if '-s' or '-t' are not defined,
        # bootrom_tool will try to use auth_sv5.auth and lk.bin.sign.
        # To avoid bootrom_tool from sending these files, pass invalid
        # values for -s and -t.
        bootrom_app.extend(['-s', '', '-t', ''])

    # udev is Linux-only; on Darwin/Windows we skip the kernel USB wait
    # and rely on aiot-bootrom's own retry loop.
    if platform.system() == 'Linux':
        udev_wait(udev_monitor)
    if args.daemon:
        try:
            return aiot_bootrom.bootrom.check_output(bootrom_app)
        except subprocess.CalledProcessError as e:
            return e.stdout
        except KeyboardInterrupt:
            return None
    else:
        return aiot_bootrom.bootrom.run(bootrom_app)
