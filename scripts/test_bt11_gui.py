import importlib.util
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('control_panel', Path(__file__).with_name('bt11-control.py'))
panel_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel_module)


class MissingDevice:
    def __enter__(self):
        raise RuntimeError('FiiO BT11 was not found.')

    def __exit__(self, *args):
        pass


class GUITests(unittest.TestCase):
    def test_codec_update_preserves_unsaved_settings(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(panel_module.ControlPanel, 'refresh'):
                panel = panel_module.ControlPanel(root)
                panel.name.set('Unsaved name')
                panel.ldac.set('Unsaved mode')
                panel.codec_busy = True
                panel.events.put(('codec', 'LDAC (660 / 606 kbps)'))
                panel.poll()
                self.assertFalse(panel.codec_busy)
                self.assertEqual(panel.name.get(), 'Unsaved name')
                self.assertEqual(panel.ldac.get(), 'Unsaved mode')
                self.assertEqual(panel.active_codec.get(), 'Active codec: LDAC (660 / 606 kbps)')
        finally:
            root.destroy()

    def test_unplugged_transmitter_keeps_refresh_available(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(panel_module, 'BT11', MissingDevice):
                panel = panel_module.ControlPanel(root)
                deadline = time.monotonic() + 2
                while panel.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertFalse(panel.busy)
                self.assertTrue(panel.failed)
                self.assertIn('not found', panel.status.get())
                available = [str(widget['text']) for widget, _ in panel.controls if str(widget['state']) != 'disabled']
                self.assertEqual(available, ['Refresh'])
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
