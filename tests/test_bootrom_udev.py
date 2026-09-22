# SPDX-License-Identifier: MIT

import types
import unittest
from unittest import mock

import aiot.bootrom
import aiot.flash


class FakeAttributes:
    def __init__(self, vendor, product):
        self.values = {
            'idVendor': vendor,
            'idProduct': product,
        }

    def asstring(self, name):
        return self.values[name]


class FakeDevice(dict):
    def __init__(self, vendor='0e8d', product='0003',
                 device_type='usb_device'):
        super().__init__(DEVTYPE=device_type)
        self.attributes = FakeAttributes(vendor, product)


class BootromUdevTest(unittest.TestCase):
    def test_accepts_mediatek_bootrom_kernel_add_event(self):
        monitor = iter([
            ('add', FakeDevice()),
        ])

        aiot.bootrom.udev_wait(monitor)

    def test_ignores_other_devices_and_actions(self):
        accepted = FakeDevice()
        monitor = iter([
            ('bind', accepted),
            ('add', FakeDevice(vendor='1234')),
            ('add', FakeDevice(product='5678')),
            ('add', FakeDevice(device_type='usb_interface')),
            ('add', accepted),
        ])

        with mock.patch.object(
                aiot.bootrom, '_is_bootrom_event',
                wraps=aiot.bootrom._is_bootrom_event) as event_match:
            aiot.bootrom.udev_wait(monitor)

        self.assertEqual(event_match.call_count, 5)

    def test_linux_monitor_uses_raw_kernel_events(self):
        monitor = mock.Mock()

        with mock.patch.object(aiot.bootrom.pyudev, 'Context') as context:
            with mock.patch.object(
                    aiot.bootrom.pyudev.Monitor, 'from_netlink',
                    return_value=monitor) as from_netlink:
                result = aiot.bootrom.create_udev_monitor()

        self.assertIs(result, monitor)
        from_netlink.assert_called_once_with(
            context.return_value, source='kernel')
        monitor.filter_by.assert_called_once_with(subsystem='usb')
        monitor.start.assert_called_once_with()

    def test_non_linux_run_does_not_use_udev_monitor(self):
        args = types.SimpleNamespace(
            path='.',
            bootstrap='setup.py',
            bootstrap_addr=0,
            bootstrap_mode='aarch64',
            daa=False,
            daemon=False,
        )

        with mock.patch.object(aiot.bootrom.platform, 'system',
                               return_value='Darwin'):
            with mock.patch.object(aiot.bootrom, 'udev_wait') as wait:
                with mock.patch.object(
                        aiot.bootrom.aiot_bootrom.bootrom, 'run',
                        return_value=0):
                    aiot.bootrom.run_bootrom(args)

        wait.assert_not_called()


class FlashUdevOrderingTest(unittest.TestCase):
    def test_monitor_starts_before_board_reset(self):
        events = []
        monitor = object()
        board = mock.Mock()
        board.download_mode_boot.side_effect = lambda: events.append('reset')
        flash = aiot.flash.Flash.__new__(aiot.flash.Flash)
        flash.check = mock.Mock(return_value=True)
        flash.initialize_board = mock.Mock(return_value=board)
        flash.handle_bootstrap = mock.Mock(return_value=True)
        flash.flash = mock.Mock()
        args = types.SimpleNamespace(
            targets=[],
            dry_run=False,
            skip_bootstrap=False,
        )

        with mock.patch.object(aiot.flash.platform, 'system',
                               return_value='Linux'):
            with mock.patch.object(
                    aiot.flash, 'create_udev_monitor',
                    side_effect=lambda: events.append('monitor') or monitor):
                flash.flash_worker(None, args)

        self.assertEqual(events, ['monitor', 'reset'])
        flash.handle_bootstrap.assert_called_once_with(
            args, None, None, monitor)


if __name__ == '__main__':
    unittest.main()
