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
    def test_paired_telemetry_tracks_connection_and_preserves_selection(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(panel_module.ControlPanel, 'refresh'):
                panel = panel_module.ControlPanel(root)
                devices = [{'name': 'WH-1000XM5', 'address': '58:18:62:21:db:68', 'connected': True},
                           {'name': 'Other', 'address': '00:11:22:33:44:55', 'connected': False}]
                panel.fill(panel.paired_tree, devices)
                status = {'devices': devices, 'codec': 'LDAC (660 / 606 kbps)', 'rssi': -67, 'bitrate_kbps': 607.2}
                panel.render_link_rows(status)
                rows = panel.paired_tree.get_children()
                self.assertEqual(panel.paired_tree.item(rows[0], 'values')[3:], ('-67 dBm', '607.2 kbps', 'LDAC (660 / 606 kbps)'))
                self.assertEqual(panel.paired_tree.item(rows[1], 'values')[3:], ('—', '—', '—'))
                self.assertEqual(panel.selected(panel.paired_tree), ('WH-1000XM5', 'Connected', '58:18:62:21:db:68'))
                devices[0]['connected'] = False
                panel.render_link_rows(status)
                selected = panel.paired_tree.selection()[0]
                self.assertEqual(panel.paired_tree.item(selected, 'values')[2:], ('58:18:62:21:db:68', '—', '—', '—'))
                devices[0]['connected'] = devices[1]['connected'] = True
                panel.render_link_rows(status)
                for row in panel.paired_tree.get_children():
                    self.assertEqual(panel.paired_tree.set(row, 'rssi'), '—')
                    self.assertIn('Shared link', panel.paired_tree.set(row, 'codec'))
        finally:
            root.update_idletasks()
            for callback in root.tk.call('after', 'info'):
                root.after_cancel(callback)
            root.destroy()

    def test_graph_leaves_gaps_between_unavailable_samples(self):
        root = tk.Tk()
        root.withdraw()
        try:
            graph = panel_module.LinkGraphs(root)
            now = time.monotonic()
            graph.samples.extend([(now-5, -67, 607), (now-4, -68, 608),
                                  (now-3, None, None), (now-2, -69, 606),
                                  (now-1, -70, 607)])
            with patch.object(graph.canvas, 'winfo_width', return_value=500), patch.object(graph.canvas, 'winfo_height', return_value=400):
                graph.draw()
            for color in ['#2166ac', '#1b7837']:
                traces = [item for item in graph.canvas.find_all() if graph.canvas.type(item) == 'line' and graph.canvas.itemcget(item, 'fill') == color]
                self.assertEqual(len(traces), 2)
                self.assertTrue(all(len(graph.canvas.coords(item)) == 4 for item in traces))
        finally:
            root.update_idletasks()
            root.destroy()

    def test_codec_update_preserves_unsaved_settings(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(panel_module.ControlPanel, 'refresh'):
                panel = panel_module.ControlPanel(root)
                panel.name.set('Unsaved name')
                panel.ldac.set('Unsaved mode')
                panel.codec_busy = True
                panel.events.put(('link', {'codec': 'LDAC (660 / 606 kbps)', 'rssi': -67, 'bitrate_kbps': 607.2}))
                panel.poll()
                self.assertFalse(panel.codec_busy)
                self.assertEqual(panel.name.get(), 'Unsaved name')
                self.assertEqual(panel.ldac.get(), 'Unsaved mode')
                self.assertEqual(panel.active_codec.get(), 'Active codec: LDAC (660 / 606 kbps)')
                self.assertIn('-67 dBm', panel.graphs.values.get())
                self.assertIn('607.2 kbps', panel.graphs.values.get())
                panel.events.put(('link', {'codec': 'Unavailable', 'rssi': None, 'bitrate_kbps': None}))
                panel.poll()
                self.assertEqual(panel.graphs.values.get(), 'RSSI: —    Bitrate: —')
                self.assertEqual(panel.name.get(), 'Unsaved name')
                panel.events.put(('link', {'codec': 'Unavailable', 'poll_error': True}))
                panel.poll()
                self.assertFalse(panel.graphs.live.get())
                self.assertIn('sampling stopped', panel.status.get())
        finally:
            root.update_idletasks()
            for callback in root.tk.call('after', 'info'):
                root.after_cancel(callback)
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
            root.update_idletasks()
            for callback in root.tk.call('after', 'info'):
                root.after_cancel(callback)
            root.destroy()


if __name__ == '__main__':
    unittest.main()
