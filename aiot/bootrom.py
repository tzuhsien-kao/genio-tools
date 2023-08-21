import platform
import subprocess

if platform.system() == 'Linux':
    import pyudev

def udev_wait():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="usb")

    for action, device in monitor:
        if 'ID_VENDOR_ID' in device and 'ID_MODEL_ID' in device:
            if device['ID_VENDOR_ID'] == '0e8d':
                if action == 'bind':
                    break

def add_bootstrap_group(parser):
    group = parser.add_argument_group('Bootstrap')
    group.add_argument('-P', '--path', type=str,
                       help='Path to image', default=".")
    group.add_argument('--skip-bootstrap', action="store_true",
                       help="Don't bootstrap the board")
    group.add_argument('--addr', type=int, default=0x201000,
                       metavar='0x201000',
                       help='Download Agent load address')
    group.add_argument('--arch', type=str, default='aarch64',
                       choices=['aarch64', 'aarch32'])
    group.add_argument('--auth', type=str, default='auth_sv5.auth',
                       metavar='auth_sv5.auth',
                       help='Authenticate file when DAA enabled')
    group.add_argument('--da', type=str, default="da.bin",
                       metavar='da.bin',
                       help='Download Agent file')
    group.add_argument('--sign', type=str, default='da.sign',
                       metavar='da.sign',
                       help='Download Agent signing file when DAA enabled')

def run_bootrom(args):
    bootrom_app = [
        'aiot-bootrom',
        '--addr', hex(args.addr),
        '--arch', args.arch,
        '--da', args.da,
    ]

    if args.auth:
        bootrom_app.extend(['--auth', args.auth])
    if args.sign:
        bootrom_app.extend(['--sign', args.sign])

    try:
        if platform.system() == 'Linux':
            udev_wait()
        subprocess.run(bootrom_app, check=True)
    except KeyboardInterrupt:
        pass
