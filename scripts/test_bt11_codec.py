import unittest
from unittest.mock import patch
from bt11 import codec_status
from test_bt11 import controller, response


class CodecTests(unittest.TestCase):
    def test_ldac_reports_negotiated_mode(self):
        for mode, rate in [(0, '990 / 909'), (1, '660 / 606'), (2, '330 / 303')]:
            self.assertEqual(codec_status(bytes([1, 8, mode])), f'LDAC ({rate} kbps)')

    def test_query_matches_mobile_app_selector(self):
        device = controller([response(113, bytes([1, 8, 1]))])
        self.assertEqual(device.active_codec(), 'LDAC (660 / 606 kbps)')
        self.assertEqual(device.device.writes[0][7:10], bytes([48, 113, 4]))

    def test_lossless_flag_and_modes(self):
        data = bytearray([1, 7, 3] + [0] * 16)
        self.assertEqual(codec_status(data), 'aptX Adaptive (High quality)')
        data[18] = 1
        self.assertEqual(codec_status(data), 'aptX Adaptive (Lossless)')
        self.assertEqual(codec_status(bytes([1, 7, 19])), 'aptX Adaptive (Lossless)')

    def test_missing_unknown_and_disconnected(self):
        self.assertIn('incomplete', codec_status(bytes([1, 8])))
        self.assertEqual(codec_status(bytes([0, 0, 0])), 'No active codec')
        self.assertEqual(codec_status(bytes([1, 255, 0])), 'Unknown codec (0xFF)')
        device = controller([])
        with patch.object(device, 'request', side_effect=RuntimeError('timeout')):
            self.assertIn('Unavailable', device.active_codec())


if __name__ == '__main__':
    unittest.main()
