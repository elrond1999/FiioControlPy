"""Connect the user's already-paired WH-1000XM5 through a native BT11 HID handle."""
import argparse
import ctypes
import queue
import threading
import time
import tkinter as tk

import hid

VID, PID = 0x0A12, 0x4007
ADDRESS = bytes([88, 24, 98, 33, 219, 104])
NAME = "WH-1000XM5"


def request(device, command, payload=b""):
    frame = bytes([255, 3, 0, len(payload), 0, 29, 48, command]) + payload
    # Native HID includes the report ID. Report 7 has 446 data bytes.
    output = bytes([7]) + frame + bytes(446 - len(frame))
    if device.write(output) != len(output):
        raise RuntimeError("BT11 could not receive the USB command.")
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        report = bytes(device.read(447, 250))
        if not report or report[0] != 8:
            continue
        frame = report[1:]
        if len(frame) >= 8 and frame[:3] == b"\xff\x03\x00" and frame[5:8] == bytes([29, 49, command]):
            size = frame[3]
            if len(frame) < 8 + size:
                raise RuntimeError("BT11 returned an incomplete response.")
            return frame[8:8 + size]
    raise RuntimeError("BT11 did not respond. Close FiiO Control and try again.")


def paired_status(device):
    payload = request(device, 14)
    if not payload or len(payload) < 1 + payload[0] * 12:
        raise RuntimeError("BT11 returned an unexpected paired-device list.")
    for index in range(payload[0]):
        row = payload[1 + index * 12:13 + index * 12]
        if row[1:7] == ADDRESS:
            return row[7] == 128
    raise RuntimeError("Your WH-1000XM5 is no longer paired with this BT11. Pair it in FiiO Control first.")


def run(status_only=False, update=print):
    devices = [d for d in hid.enumerate(VID, PID) if d["usage_page"] == 0xFF00 and d["usage"] == 3]
    if not devices:
        raise RuntimeError("FiiO BT11 was not found. Plug it into this PC and try again.")
    if len(devices) != 1:
        raise RuntimeError("More than one BT11 is plugged in. Leave only the intended transmitter connected.")
    device = hid.device()
    try:
        device.open_path(devices[0]["path"])
        connected = paired_status(device)
        if status_only:
            update("Connected" if connected else "Disconnected")
            return connected
        if connected:
            update("WH-1000XM5 is already connected.")
            return True
        update("Connecting… Keep your headphones switched on.")
        request(device, 16, bytes([0]) + ADDRESS + bytes([0]))
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            time.sleep(1)
            if paired_status(device):
                update("Connected to WH-1000XM5.")
                return True
        raise RuntimeError("Headphones did not connect. Switch them on, bring them nearby, and try again.")
    finally:
        device.close()


def gui():
    root = tk.Tk()
    root.title("Connect WH-1000XM5")
    root.geometry("440x190")
    root.resizable(False, False)
    tk.Label(root, text=NAME, font=("Segoe UI", 18)).pack(pady=(20, 8))
    status = tk.StringVar(value="Opening FiiO BT11…")
    tk.Label(root, textvariable=status, font=("Segoe UI", 10), wraplength=400).pack(padx=20)
    messages = queue.Queue()
    def worker():
        try:
            run(update=lambda message: messages.put(("status", message)))
            messages.put(("success", ""))
        except Exception as error:
            messages.put(("error", str(error)))
    def poll():
        while not messages.empty():
            kind, message = messages.get_nowait()
            if kind == "status":
                status.set(message)
            elif kind == "success":
                root.after(1500, root.destroy)
            else:
                status.set(message)
                tk.Button(root, text="Close", command=root.destroy).pack(pady=12)
        root.after(100, poll)
    threading.Thread(target=worker, daemon=True).start()
    root.after(100, poll)
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Read connection status without connecting")
    parser.add_argument("--cli", action="store_true", help="Connect without a graphical window")
    args = parser.parse_args()
    # Prevent overlapping launches from consuming one another's HID responses.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, False, "Local\\FiioBT11WH1000XM5")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    duplicate = ctypes.get_last_error() == 183
    try:
        if not duplicate:
            if args.status or args.cli:
                try:
                    run(status_only=args.status)
                except Exception as error:
                    parser.exit(1, str(error) + "\n")
            else:
                gui()
    finally:
        kernel.CloseHandle(mutex)
