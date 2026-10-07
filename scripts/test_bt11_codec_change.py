import unittest
from unittest.mock import Mock, call
from bt11 import BT11


class CodecChangeTests(unittest.TestCase):
    def device(self):
        d = BT11()
        d.request = Mock(return_value=bytes([8, 2, 1, 0]))
        d.byte = Mock(return_value=1)
        d.devices = Mock()
        d.device_action = Mock()
        d.connect = Mock()
        return d

    def assert_connection_untouched(self, device):
        device.devices.assert_not_called()
        device.device_action.assert_not_called()
        device.connect.assert_not_called()

    def test_codec_change_applies_without_disconnect_or_reconnect(self):
        d = self.device()
        d.set_codecs([], 1, 3)
        self.assertEqual(d.request.call_args_list, [call(6), call(7, bytes([2, 1, 0]))])
        self.assert_connection_untouched(d)

    def test_unchanged_settings_do_not_interrupt_audio(self):
        d = self.device()
        d.set_codecs([8], 1, 3)
        self.assert_connection_untouched(d)
        self.assertEqual(d.request.call_count, 1)

    def test_write_failure_reports_recovery_without_connection_commands(self):
        d = self.device()
        d.request.side_effect = [bytes([8, 2, 1, 0]), RuntimeError('timeout')]
        with self.assertRaisesRegex(RuntimeError, 'unplug and reinsert'):
            d.set_codecs([], 1, 3)
        self.assert_connection_untouched(d)
