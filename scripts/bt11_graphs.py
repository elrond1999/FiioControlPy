"""Dependency-free live plots for the experimentally inferred BT11 link fields."""
import math
import time
import tkinter as tk
from collections import deque
from tkinter import ttk


class LinkGraphs(ttk.Frame):
    WINDOW = 120

    def __init__(self, parent):
        super().__init__(parent, padding=16)
        self.samples = deque(maxlen=240)
        self.live = tk.BooleanVar(value=True)
        self.message = tk.StringVar(value='Waiting for link measurements…')
        self.values = tk.StringVar(value='RSSI: —    Bitrate: —')
        ttk.Label(self, text='Live link measurements', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Signal strength and audio bitrate from your BT11.', wraplength=680).pack(anchor='w', pady=(6, 12))
        row = ttk.Frame(self)
        row.pack(fill='x')
        ttk.Checkbutton(row, text='Live sampling (1 s)', variable=self.live).pack(side='left')
        ttk.Button(row, text='Clear history', command=self.clear).pack(side='right')
        ttk.Label(self, textvariable=self.values, font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=12)
        self.canvas = tk.Canvas(self, background='#ffffff', highlightthickness=0, height=440)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self.draw())
        ttk.Label(self, textvariable=self.message, wraplength=680).pack(anchor='w', pady=(12, 0))
        ttk.Label(self, text='Last 120 seconds • gaps mean sampling was paused, busy, or unavailable.', wraplength=680).pack(anchor='w', pady=(6, 0))

    def clear(self):
        self.samples.clear()
        self.draw()

    def update_status(self, status=None, message=None):
        status = status or {}
        rssi, bitrate = status.get('rssi'), status.get('bitrate_kbps')
        self.samples.append((time.monotonic(), rssi, bitrate))
        self.values.set(f"RSSI: {rssi if rssi is not None else '—'}" +
                        (" dBm" if rssi is not None else '') +
                        f"    Bitrate: {f'{bitrate:.1f} kbps' if bitrate is not None else '—'}")
        self.message.set(message or status.get('codec', 'Measurements unavailable'))
        self.draw()

    def draw(self):
        c = self.canvas
        c.delete('all')
        width, height = c.winfo_width(), c.winfo_height()
        if width < 150 or height < 150:
            return
        now = time.monotonic()
        visible = [s for s in self.samples if now - self.WINDOW <= s[0] <= now]
        for plot, (field, title, color, default) in enumerate([
                (1, 'RSSI (dBm)', '#2166ac', (-100, -30)),
                (2, 'Bitrate (kbps)', '#1b7837', (0, 1000))]):
            left, right = 65, width - 18
            top, bottom = plot * height / 2 + 28, (plot + 1) * height / 2 - 30
            vals = [s[field] for s in visible if s[field] is not None]
            lo, hi = default
            if vals:
                step = 10 if field == 1 else 100
                lo = min(lo, math.floor(min(vals) / step) * step)
                hi = max(hi, math.ceil(max(vals) / step) * step)
            c.create_text(left, top - 16, text=title, anchor='w', fill=color, font=('Segoe UI', 10, 'bold'))
            for tick in range(5):
                y = top + (bottom - top) * tick / 4
                value = hi - (hi - lo) * tick / 4
                c.create_line(left, y, right, y, fill='#e5eaf0')
                c.create_text(left - 8, y, text=f'{value:g}', anchor='e', fill='#526477')
            for age in (120, 90, 60, 30, 0):
                x = right - age / self.WINDOW * (right - left)
                c.create_text(x, bottom + 14, text=f'−{age}s' if age else 'now', fill='#526477')
            segment = []
            previous = None
            def flush():
                if len(segment) >= 4:
                    c.create_line(*segment, fill=color, width=2)
                elif segment:
                    x, y = segment
                    c.create_oval(x-2, y-2, x+2, y+2, fill=color, outline=color)
                segment.clear()
            for sample in visible:
                timestamp, value = sample[0], sample[field]
                if value is None or (previous is not None and timestamp - previous > 2.5):
                    flush()
                if value is not None:
                    segment.extend([right - (now-timestamp)/self.WINDOW*(right-left),
                                    bottom - (value-lo)/(hi-lo)*(bottom-top)])
                previous = timestamp
            flush()
