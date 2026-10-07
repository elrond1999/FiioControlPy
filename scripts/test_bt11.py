import unittest
from bt11 import BT11, decode, frame


class FakeHID:
    def __init__(self, reports=()):
        self.reports, self.writes = list(reports), []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, length, timeout):
        return self.reports.pop(0) if self.reports else []


def response(command, payload=b'', feature=24):
    return bytes([8, 255, 3, 0, len(payload), 0, 29, (feature << 1) | 1, command]) + payload


def controller(reports):
    device = BT11()
    device.device = FakeHID(reports)
    device.notifications = []
    return device


class ProtocolTests(unittest.TestCase):
    def test_reply_matching_preserves_discovery_events(self):
        device = controller([response(129, b'notification'), response(82, b'wrong command'), response(10, b'\x00')])
        self.assertEqual(device.request(10), b'\x00')
        self.assertEqual(device.notifications, [(49, 129, b'notification')])
        self.assertEqual(len(device.device.writes[0]), 447)

    def test_core_reply_does_not_match_app_feature(self):
        device = controller([response(5, b'wrong feature'), response(5, b'1.1.4', feature=0)])
        self.assertEqual(device.request(5, feature=0), b'1.1.4')

    def test_incomplete_frame_rejected(self):
        report = bytearray(response(14, b'\x00'))
        report[4] = 10
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            decode(report)

    def test_unrelated_report_ignored(self):
        self.assertIsNone(decode(bytes([6]) + bytes(62)))

    def test_utf8_name_limit_checked_before_write(self):
        device = controller([])
        with self.assertRaises(ValueError):
            device.set_name('é' * 17)
        self.assertFalse(device.device.writes)

    def test_brightness_bounds_checked_before_write(self):
        device = controller([])
        for value in [-1, 8]:
            with self.assertRaises(ValueError):
                device.set_brightness(value)
        self.assertFalse(device.device.writes)

    def test_malformed_pairing_list_rejected(self):
        device = controller([response(14, b'\x02' + bytes(12))])
        with self.assertRaisesRegex(RuntimeError, 'paired-device list'):
            device.devices()

    def test_invalid_address_checked_before_write(self):
        device = controller([])
        with self.assertRaises(ValueError):
            device.device_action(16, '58:18:62')
        self.assertFalse(device.device.writes)


if __name__ == '__main__':
    unittest.main()
