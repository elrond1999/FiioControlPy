import unittest
from bt11 import parse_link_status
from test_bt11 import controller, response


class LinkTests(unittest.TestCase):
    def test_measured_payload_signed_rssi_and_bitrate(self):
        raw = bytes.fromhex('010801010100000028440900abff76fe0000000000000000')
        status = parse_link_status(raw)
        self.assertEqual(status['rssi'], -85)
        self.assertEqual(status['bitrate_kbps'], 607.272)
        self.assertEqual(controller([response(113, raw)]).link_status(), status)

    def test_disconnected_and_short_responses_do_not_show_old_measurements(self):
        for data in [b'', bytes([1, 8, 1]), bytes(24)]:
            status = parse_link_status(data)
            self.assertIsNone(status['rssi'])
            self.assertIsNone(status['bitrate_kbps'])


if __name__ == '__main__':
    unittest.main()
