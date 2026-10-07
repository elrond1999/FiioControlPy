import unittest
from unittest.mock import Mock, patch
from bt11 import BT11


class CodecChangeTests(unittest.TestCase):
    def device(self):
        d = BT11()
        d.request = Mock(return_value=bytes([8, 2, 1, 0]))
        d.byte = Mock(return_value=1)
        d.device_action = Mock()
        d.connect = Mock()
        return d

    def test_disconnect_confirm_write_reconnect_order(self):
        d = self.device()
        d.devices = Mock(side_effect=[[{'address': 'headset', 'connected': True}],
                                      [{'address': 'headset', 'connected': True}],
                                      [{'address': 'headset', 'connected': False}]])
        trace = Mock()
        for name in ['request', 'devices', 'device_action', 'connect']:
            trace.attach_mock(getattr(d, name), name)
        with patch('bt11.time.sleep'):
            d.set_codecs([], 1, 3)
        calls = trace.mock_calls
        disconnect = next(i for i,c in enumerate(calls) if c == unittest.mock.call.device_action(17, 'headset'))
        write = next(i for i,c in enumerate(calls) if c == unittest.mock.call.request(7, bytes([2,1,0])))
        reconnect = next(i for i,c in enumerate(calls) if c == unittest.mock.call.connect('headset'))
        self.assertLess(disconnect, write)
        self.assertEqual(calls[write-1], unittest.mock.call.devices())
        self.assertLess(write, reconnect)

    def test_failed_disconnect_never_writes_codecs(self):
        d = self.device()
        d.devices = Mock(return_value=[{'address': 'headset', 'connected': True}])
        with patch('bt11.time.monotonic', side_effect=[0, 11]):
            with self.assertRaisesRegex(RuntimeError, 'not changed'):
                d.set_codecs([], 1, 3)
        self.assertEqual(d.request.call_count, 1)
        d.connect.assert_not_called()

    def test_unchanged_settings_do_not_interrupt_audio(self):
        d = self.device()
        d.devices = Mock()
        d.set_codecs([8], 1, 3)
        d.devices.assert_not_called()
        d.device_action.assert_not_called()
        self.assertEqual(d.request.call_count, 1)

    def test_write_failure_stops_without_reconnecting(self):
        d = self.device()
        d.request.side_effect = [bytes([8,2,1,0]), RuntimeError('timeout')]
        d.devices = Mock(side_effect=[[{'address': 'headset', 'connected': True}], []])
        with self.assertRaisesRegex(RuntimeError, 'unplug and reinsert'):
            d.set_codecs([], 1, 3)
        d.connect.assert_not_called()
