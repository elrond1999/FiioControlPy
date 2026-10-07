"""Native Windows settings panel for FiiO BT11."""
import argparse
import json
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from bt11 import APTX_MODES, BT11, CODECS, LDAC_MODES, PAIRING_MODES
from bt11_graphs import LinkGraphs


class ControlPanel:
    def __init__(self, root, smoke=False):
        self.root, self.smoke = root, smoke
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy, self.closing, self.failed = False, False, False
        self.current, self.discovered = None, []
        self.codec_busy = False
        self.controls = []
        root.title('FiiO BT11 Control')
        root.geometry('760x900')
        root.minsize(700, 880)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root)
        style.theme_use('vista' if 'vista' in style.theme_names() else 'clam')
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        self.status = tk.StringVar(value='Reading BT11 settings…')
        self.name = tk.StringVar()
        self.brightness = tk.IntVar(value=0)
        self.ldac, self.aptx, self.pairing = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.codec_vars = {code: tk.BooleanVar() for code in CODECS}
        self.firmware = tk.StringVar(value='Firmware: —')
        self.active_codec = tk.StringVar(value='Active codec: —')
        tabs = ttk.Notebook(root)
        tabs.pack(fill='both', expand=True)
        settings = ttk.Frame(tabs)
        tabs.add(settings, text='Settings')
        self.graphs = LinkGraphs(tabs)
        tabs.add(self.graphs, text='Live RSSI & bitrate')
        outer = ttk.Frame(settings, padding=18)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x')
        ttk.Label(header, text='FiiO BT11', style='Title.TLabel').pack(side='left')
        self.button(header, 'Refresh', self.refresh).pack(side='right')
        ttk.Label(outer, text='Native USB control', foreground='#526477').pack(anchor='w')
        ttk.Label(outer, textvariable=self.status, wraplength=710).pack(anchor='w', pady=(8, 12))
        device = ttk.LabelFrame(outer, text='Transmitter', padding=12)
        device.pack(fill='x', pady=(0, 10))
        ttk.Label(device, text='Bluetooth name').grid(row=0, column=0, sticky='w')
        self.entry(device, self.name).grid(row=0, column=1, sticky='ew', padx=10)
        self.button(device, 'Save name', self.save_name).grid(row=0, column=2)
        ttk.Label(device, text='LED brightness (0–7)').grid(row=1, column=0, sticky='w', pady=(10, 0))
        spin = ttk.Spinbox(device, from_=0, to=7, textvariable=self.brightness, width=8, state='readonly')
        self.controls.append((spin, 'readonly'))
        spin.grid(row=1, column=1, sticky='w', padx=10, pady=(10, 0))
        self.button(device, 'Save brightness', self.save_brightness).grid(row=1, column=2, pady=(10, 0))
        device.columnconfigure(1, weight=1)
        codecs = ttk.LabelFrame(outer, text='Bluetooth codecs', padding=12)
        codecs.pack(fill='x', pady=(0, 10))
        ttk.Label(codecs, textvariable=self.active_codec, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 6))
        checks = ttk.Frame(codecs)
        checks.pack(fill='x')
        for code, label in CODECS.items():
            check = ttk.Checkbutton(checks, text=label, variable=self.codec_vars[code])
            check.pack(side='left', padx=(0, 12))
            self.controls.append((check, 'normal'))
        ttk.Label(codecs, text='SBC remains available. Enabled codecs depend on what the headphones support.').pack(anchor='w', pady=6)
        quality = ttk.Frame(codecs)
        quality.pack(fill='x')
        ttk.Label(quality, text='LDAC quality').grid(row=0, column=0, sticky='w')
        self.combo(quality, self.ldac, LDAC_MODES, 40).grid(row=0, column=1, sticky='w', padx=12)
        ttk.Label(quality, text='aptX Adaptive').grid(row=1, column=0, sticky='w', pady=8)
        self.combo(quality, self.aptx, APTX_MODES, 40).grid(row=1, column=1, sticky='w', padx=12)
        self.button(quality, 'Save codecs', self.save_codecs).grid(row=0, column=2, rowspan=2, padx=8)
        devices = ttk.LabelFrame(outer, text='Paired headphones', padding=10)
        devices.pack(fill='x', pady=(0, 10))
        self.paired_tree = self.tree(devices, 3)
        row = ttk.Frame(devices)
        row.pack(fill='x', pady=(8, 0))
        self.button(row, 'Connect selected', lambda: self.device_action(16)).pack(side='left')
        self.button(row, 'Disconnect', lambda: self.device_action(17)).pack(side='left', padx=8)
        self.button(row, 'Forget selected', lambda: self.device_action(19)).pack(side='left')
        pairing = ttk.LabelFrame(outer, text='Pairing & discovery', padding=10)
        pairing.pack(fill='x', pady=(0, 10))
        mode_row = ttk.Frame(pairing)
        mode_row.pack(fill='x', pady=(0, 8))
        ttk.Label(mode_row, text='Pairing mode').pack(side='left')
        self.combo(mode_row, self.pairing, PAIRING_MODES, 10).pack(side='left', padx=8)
        self.button(mode_row, 'Apply mode', self.save_pairing).pack(side='left')
        self.button(mode_row, 'Scan nearby (12 s)', self.scan).pack(side='left', padx=8)
        self.stop_button = ttk.Button(mode_row, text='Stop scan', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left')
        self.found_tree = self.tree(pairing, 3)
        self.button(pairing, 'Pair & connect selected', self.pair_selected).pack(anchor='w', pady=(8, 0))
        bottom = ttk.Frame(outer)
        bottom.pack(fill='x')
        ttk.Label(bottom, textvariable=self.firmware).pack(side='left')
        self.button(bottom, 'FiiO firmware updater ↗', self.open_updater).pack(side='right')
        maintenance = ttk.Frame(outer)
        maintenance.pack(fill='x', pady=(10, 0))
        self.button(maintenance, 'Clear all pairings…', lambda: self.maintenance(20)).pack(side='left')
        self.button(maintenance, 'Restore defaults…', lambda: self.maintenance(121)).pack(side='left', padx=8)
        root.after(100, self.poll)
        root.after(1000, self.refresh_codec)
        self.refresh()

    def button(self, parent, text, command):
        widget = ttk.Button(parent, text=text, command=command)
        self.controls.append((widget, 'normal'))
        return widget

    def entry(self, parent, variable):
        widget = ttk.Entry(parent, textvariable=variable)
        self.controls.append((widget, 'normal'))
        return widget

    def combo(self, parent, variable, mapping, width):
        widget = ttk.Combobox(parent, textvariable=variable, values=list(mapping.values()), width=width, state='readonly')
        self.controls.append((widget, 'readonly'))
        return widget

    def tree(self, parent, height):
        tree = ttk.Treeview(parent, columns=('name', 'status', 'address'), show='headings', height=height, selectmode='browse')
        for column, title, width in [('name', 'Name', 260), ('status', 'Status', 100), ('address', 'Bluetooth address', 210)]:
            tree.heading(column, text=title)
            tree.column(column, width=width, minwidth=60)
        tree.pack(fill='x')
        return tree

    def submit(self, label, operation):
        if self.busy:
            return
        if self.codec_busy:
            self.root.after(100, lambda: self.submit(label, operation) if not self.closing else None)
            return
        self.busy = True
        self.stop.clear()
        self.status.set(label)
        for widget, _ in self.controls:
            widget.configure(state='disabled')
        def worker():
            try:
                with BT11() as device:
                    operation(device)
                    snapshot = device.snapshot()
                self.events.put(('snapshot', snapshot))
                self.events.put(('done', 'Ready — settings read from BT11.'))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def refresh(self):
        self.submit('Reading BT11 settings…', lambda _: None)

    def refresh_codec(self):
        if self.closing or self.smoke:
            return
        if not self.graphs.live.get():
            self.graphs.update_status(message='Live sampling paused')
        elif not self.busy and not self.codec_busy and self.current and not self.failed:
            self.codec_busy = True
            def worker():
                try:
                    with BT11() as device:
                        status = device.link_status()
                except Exception:
                    status = {'codec': 'Unavailable (transmitter busy or disconnected)'}
                self.events.put(('link', status))
            threading.Thread(target=worker, daemon=True).start()
        else:
            self.graphs.update_status(message='Sampling waits while a device operation is running' if self.busy or self.codec_busy else 'Refresh settings to resume sampling')
        self.root.after(1000, self.refresh_codec)

    @staticmethod
    def mode(variable, mapping):
        return next(key for key, label in mapping.items() if label == variable.get())

    def save_name(self):
        name = self.name.get()
        if not name or len(name.encode('utf-8')) > 32 or '\x00' in name:
            messagebox.showerror('Bluetooth name', 'Enter a name containing 1–32 UTF-8 bytes.', parent=self.root)
            return
        self.submit('Saving Bluetooth name…', lambda d: d.set_name(name))

    def save_brightness(self):
        value = self.brightness.get()
        self.submit('Saving LED brightness…', lambda d: d.set_brightness(value))

    def save_codecs(self):
        enabled = [c for c, variable in self.codec_vars.items() if variable.get()]
        # Preserve LHDC if a firmware version exposes it outside the web page's controls.
        if self.current and 9 in self.current['codecs']:
            enabled.append(9)
        try:
            ldac, aptx = self.mode(self.ldac, LDAC_MODES), self.mode(self.aptx, APTX_MODES)
        except StopIteration:
            messagebox.showerror('Codec modes', 'Select valid LDAC and aptX modes before saving.', parent=self.root)
            return
        self.submit('Saving codecs and quality modes…', lambda d: d.set_codecs(enabled, ldac, aptx))

    def save_pairing(self):
        mode = self.mode(self.pairing, PAIRING_MODES)
        self.submit('Applying pairing mode…', lambda d: d.set_pairing(mode))

    def selected(self, tree):
        selection = tree.selection()
        if not selection:
            messagebox.showinfo('Select headphones', 'Select a device from the list first.', parent=self.root)
            return None
        return tree.item(selection[0], 'values')

    def device_action(self, command):
        selected = self.selected(self.paired_tree)
        if not selected:
            return
        name, _, address = selected
        if command == 19 and not messagebox.askyesno('Forget headphones', f'Remove {name} from the BT11 pairing list?', parent=self.root):
            return
        def operation(device):
            if command == 16:
                device.connect(address, self.stop)
            else:
                device.device_action(command, address)
                self.stop.wait(0.5)
        self.submit('Updating headphone connection…', operation)

    def scan(self):
        if self.busy:
            return
        mode = self.mode(self.pairing, PAIRING_MODES)
        if mode == 0:
            mode = 2
        if mode == 1 and not messagebox.askyesno('Automatic pairing', 'Auto mode may pair nearby headphones automatically. Start discovery?', parent=self.root):
            return
        self.discovered = []
        self.fill(self.found_tree, [])
        self.submit('Scanning nearby devices for 12 seconds… Previous pairing mode will be restored.', lambda d: d.scan(mode, stop=self.stop, update=lambda items: self.events.put(('found', items))))
        self.stop_button.configure(state='normal')

    def pair_selected(self):
        selected = self.selected(self.found_tree)
        if not selected:
            return
        name, _, address = selected
        def operation(device):
            device.device_action(18, address)
            self.stop.wait(0.3)
            device.connect(address, self.stop)
        self.submit(f'Pairing and connecting {name}…', operation)

    def maintenance(self, command):
        question = 'Remove every paired device from the BT11?' if command == 20 else 'Restore the BT11 to its factory settings? This can clear your preferences and require pairing again.'
        if messagebox.askyesno('Confirm reset', question, parent=self.root):
            self.submit('Resetting BT11…', lambda d: d.request(command))

    def open_updater(self):
        webbrowser.open('https://fiiocontrol.fiio.com/jp-bt-device')

    def fill(self, tree, devices):
        selected = tree.selection()
        address = tree.item(selected[0], 'values')[2] if selected else None
        tree.delete(*tree.get_children())
        for device in devices:
            item = tree.insert('', 'end', values=(device['name'], 'Connected' if device['connected'] else 'Disconnected', device['address']))
            if address == device['address'] or (address is None and device['name'] == 'WH-1000XM5'):
                tree.selection_set(item)

    def render(self, snapshot):
        self.current = snapshot
        self.name.set(snapshot['name'])
        self.brightness.set(snapshot['brightness'])
        for code, variable in self.codec_vars.items():
            variable.set(code in snapshot['codecs'])
        self.ldac.set(LDAC_MODES.get(snapshot['ldac_mode'], f"Unknown ({snapshot['ldac_mode']})"))
        self.aptx.set(APTX_MODES.get(snapshot['aptx_mode'], f"Unknown ({snapshot['aptx_mode']})"))
        self.pairing.set(PAIRING_MODES.get(snapshot['pairing_mode'], f"Unknown ({snapshot['pairing_mode']})"))
        self.firmware.set('Firmware: ' + snapshot['firmware'])
        self.active_codec.set('Active codec: ' + snapshot.get('active_codec', 'Unavailable'))
        self.fill(self.paired_tree, snapshot['devices'])

    def poll(self):
        while not self.events.empty():
            kind, data = self.events.get_nowait()
            if kind == 'snapshot':
                self.render(data)
            elif kind in ('codec', 'link'):
                self.codec_busy = False
                if kind == 'link':
                    self.graphs.update_status(data)
                    self.active_codec.set('Active codec: ' + data['codec'])
                else:
                    self.active_codec.set('Active codec: ' + data)
                if self.closing:
                    self.root.destroy()
                    return
            elif kind == 'found':
                self.discovered = data
                self.fill(self.found_tree, data)
            elif kind in ('done', 'error'):
                self.busy = False
                self.failed = kind == 'error'
                self.status.set(('Operation failed: ' if self.failed else '') + data)
                if self.failed:
                    self.active_codec.set('Active codec: Unavailable')
                for widget, state in self.controls:
                    is_refresh = isinstance(widget, ttk.Button) and widget['text'] == 'Refresh'
                    widget.configure(state=state if self.current and not self.failed else ('normal' if is_refresh else 'disabled'))
                self.stop_button.configure(state='disabled')
                if self.closing or self.smoke:
                    self.root.after(100, self.root.destroy)
                    return
        self.root.after(100, self.poll)

    def close(self):
        if self.busy or self.codec_busy:
            self.closing = True
            self.stop.set()
            self.root.withdraw()
        else:
            self.root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnose', action='store_true', help='Read current settings as JSON without modifying anything')
    parser.add_argument('--smoke-test', action='store_true', help='Build GUI, read the device, and exit')
    args = parser.parse_args()
    if args.diagnose:
        with BT11() as device:
            print(json.dumps(device.snapshot(), indent=2))
    else:
        root = tk.Tk()
        panel = ControlPanel(root, args.smoke_test)
        root.mainloop()
        if panel.failed:
            raise SystemExit(1)
