import platform
import aiot_bootrom.bootrom

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
    group.add_argument('-P', '--path', type=str, help='Path to image',
        default=".")
    group.add_argument('--skip-bootstrap', action="store_true",
        help="Don't bootstrap the board")
    group.add_argument('--bootstrap', type=str, default='lk.bin',
        metavar='lk.bin',
        help='bootstrap binary used for flashing (default: lk.bin)')
    group.add_argument('--bootstrap-sign', type=str, default='lk.sign',
        metavar='lk.sign',
        help='bootstrap binary signature used for flashing with DAA enabled (default: lk.sign)')
    group.add_argument('--bootstrap-auth', type=str, default='auth_sv5.auth',
        metavar='auth_sv5.auth',
        help='authentication file used for flashing with DAA enabled (default: auth_sv5.auth)')
    group.add_argument('--daa', action="store_true",
        help="flash with DAA enabled")
    group.add_argument('--bootstrap-addr', type=int, default=0x201000,
        metavar='0x201000',
        help='Address where the bootstrap binary will be loaded (default: 0x201000)')
    group.add_argument('--bootstrap-mode', type=str, default='aarch64',
                       choices=['aarch64', 'aarch32'])

def run_bootrom(args):
    bootrom_app = [
        'aiot-bootrom',
        '--bootstrap', args.path + '/' + args.bootstrap,
        '--bootstrap-addr', hex(args.bootstrap_addr),
        '--bootstrap-mode', args.bootstrap_mode,
    ]

    if args.daa:
       bootrom_app.extend(['-s', args.bootstrap_sign, '-t', args.bootstrap_auth])
    else:
       # By default, if '-s' or '-t' are not defined,
       # bootrom_tool will try to use auth_sv5.auth and lk.bin.sign
       # To avoid bootrom_tool from sending these files, pass invalid values for -s and -t
       bootrom_app.extend(['-s', '', '-t', ''])

    if platform.system() == 'Linux':
        udev_wait()
    return aiot_bootrom.bootrom.run(bootrom_app)
