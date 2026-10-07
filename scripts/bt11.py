"""Native BT11 control, mapped from the user's mirrored FiiO web app."""
import ctypes
import time
from contextlib import contextmanager

import hid

VID, PID = 0x0A12, 0x4007
CODECS = {8: 'LDAC', 7: 'aptX Adaptive', 6: 'aptX HD', 3: 'aptX', 5: 'aptX LL'}
LDAC_MODES = {0: 'Audio quality (990 / 909 kbps)', 1: 'Balanced (660 / 606 kbps)', 2: 'Connection quality (330 / 303 kbps)'}
APTX_MODES = {2: 'Low latency', 3: 'High quality', 19: 'Lossless'}
PAIRING_MODES = {0: 'Close', 1: 'Auto', 2: 'Manual'}


def codec_status(data):
    """Decode command 0x71, as used by FiiO Control Android 4.6.0."""
    if len(data) < 3:
        return 'Unavailable (incomplete response)'
    codec, mode = data[1:3]
    names = {0: 'No active codec', 1: 'SBC', 3: 'aptX', 4: 'aptX LL v1',
             5: 'aptX LL', 6: 'aptX HD', 9: 'LHDC',
             16: 'aptX Adaptive (LE Audio)', 17: 'LC3 (LE Audio)'}
    if codec == 8:
        rates = {0: '990 / 909', 1: '660 / 606', 2: '330 / 303'}
        return f'LDAC ({rates[mode]} kbps)' if mode in rates else 'LDAC'
    if codec == 7:
        if mode == 19 or (mode == 3 and len(data) > 18 and data[18] == 1):
            return 'aptX Adaptive (Lossless)'
        return {2: 'aptX Adaptive (Low latency)', 3: 'aptX Adaptive (High quality)'}.get(mode, 'aptX Adaptive')
    return names.get(codec, f'Unknown codec (0x{codec:02X})')


def parse_link_status(data):
    """Experimental fields inferred from movement measurements, not documented."""
    available = len(data) >= 16 and data[1] != 0
    return {'codec': codec_status(data),
            'rssi': int.from_bytes(data[12:14], 'little', signed=True) if available else None,
            'bitrate_kbps': int.from_bytes(data[8:12], 'little') / 1000 if available else None}


def frame(command, payload=b'', feature=24):
    if len(payload) > 255:
        raise ValueError('Payload is too large.')
    return bytes([255, 3, 0, len(payload), 0, 29, feature << 1, command]) + bytes(payload)


def decode(report):
    if not report or report[0] != 8:
        return None
    data = bytes(report[1:])
    if len(data) < 8 or data[:3] != b'\xff\x03\x00' or data[5] != 29:
        return None
    length = data[3]
    if len(data) < 8 + length:
        raise RuntimeError('BT11 returned an incomplete response.')
    return data[6], data[7], data[8:8 + length]


@contextmanager
def exclusive():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, False, 'Local\\FiioBT11WH1000XM5')
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    duplicate = ctypes.get_last_error() == 183
    try:
        if duplicate:
            raise RuntimeError('Another BT11 operation is running. Try again when it finishes.')
        yield
    finally:
        kernel.CloseHandle(handle)


class BT11:
    def __enter__(self):
        self.lock = exclusive()
        self.lock.__enter__()
        self.device = None
        self.notifications = []
        try:
            found = [d for d in hid.enumerate(VID, PID) if d['usage_page'] == 0xFF00 and d['usage'] == 3]
            if not found:
                raise RuntimeError('FiiO BT11 was not found. Plug it into this PC and refresh.')
            if len(found) != 1:
                raise RuntimeError('More than one BT11 is plugged in. Leave only the intended transmitter connected.')
            self.device = hid.device()
            self.device.open_path(found[0]['path'])
            return self
        except Exception:
            if self.device is not None:
                self.device.close()
            self.lock.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        try:
            self.device.close()
        finally:
            self.lock.__exit__(*args)

    def send(self, command, payload=b'', feature=24):
        data = frame(command, payload, feature)
        report = bytes([7]) + data + bytes(446 - len(data))
        if self.device.write(report) != len(report):
            raise RuntimeError('BT11 could not receive the USB command.')

    def request(self, command, payload=b'', feature=24):
        self.send(command, payload, feature)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            response = decode(self.device.read(447, 250))
            if response is None:
                continue
            response_feature, response_command, data = response
            if (response_feature, response_command) == ((feature << 1) | 1, command):
                return data
            if response_command >= 128:
                self.notifications.append(response)
        raise RuntimeError('BT11 did not respond. Close FiiO Control and try again.')

    def byte(self, command):
        result = self.request(command)
        if not result:
            raise RuntimeError(f'Empty response for BT11 setting {command}.')
        return result[0]

    def devices(self):
        data = self.request(14)
        if not data or len(data) < 1 + data[0] * 12:
            raise RuntimeError('BT11 returned an unexpected paired-device list.')
        result = []
        for index in range(data[0]):
            row = data[1 + index * 12:13 + index * 12]
            if not any(row[8:12]):
                continue
            address = row[1:7]
            name = self.request(15, b'\x00' + address + b'\x00').decode('utf-8', errors='replace').rstrip('\x00')
            result.append({'name': name, 'address': address.hex(':'), 'connected': row[7] == 128})
        return result

    def snapshot(self):
        return {
            'name': self.request(0).decode('utf-8', errors='replace').rstrip('\x00'),
            'brightness': self.byte(82), 'codecs': list(self.request(6)),
            'ldac_mode': self.byte(66), 'aptx_mode': self.byte(64),
            'pairing_mode': self.byte(10),
            'firmware': self.request(5, feature=0).decode('utf-8', errors='replace').rstrip('\x00'),
            'devices': self.devices(),
            'active_codec': self.active_codec(),
        }

    def active_codec(self):
        return self.link_status()['codec']

    def link_status(self):
        # The mobile app sends selector 4; an empty payload gets no reply.
        # Older firmware may not implement this optional status command.
        try:
            return parse_link_status(self.request(0x71, b'\x04'))
        except RuntimeError:
            return {'codec': 'Unavailable (device did not respond)', 'rssi': None, 'bitrate_kbps': None}

    def set_name(self, name):
        encoded = name.encode('utf-8')
        if not encoded or len(encoded) > 32 or '\x00' in name:
            raise ValueError('Name must contain 1–32 UTF-8 bytes and no null characters.')
        self.request(1, encoded)

    def set_brightness(self, value):
        if value not in range(8):
            raise ValueError('LED brightness must be between 0 and 7.')
        self.request(83, bytes([value]))

    def set_codecs(self, codecs, ldac_mode, aptx_mode):
        if ldac_mode not in LDAC_MODES or aptx_mode not in APTX_MODES:
            raise ValueError('Unknown codec quality mode.')
        # The web app always appends the mandatory base codecs.
        values = list(dict.fromkeys([c for c in codecs if c not in (0, 1, 2)]))
        if any(c not in (*CODECS, 9) for c in values):
            raise ValueError('Unknown Bluetooth codec.')
        self.request(7, bytes(values + [2, 1, 0]))
        if 8 in values:
            self.request(67, bytes([ldac_mode]))
        if 7 in values:
            self.request(65, bytes([aptx_mode]))

    def set_pairing(self, value):
        if value not in PAIRING_MODES:
            raise ValueError('Unknown pairing mode.')
        self.request(11, bytes([value]))

    def device_action(self, command, address):
        if command not in (16, 17, 18, 19):
            raise ValueError('Unknown device action.')
        address = bytes.fromhex(address.replace(':', ''))
        if len(address) != 6:
            raise ValueError('Bluetooth address must have six bytes.')
        self.request(command, b'\x00' + address + b'\x00')

    def connect(self, address, stop=None):
        self.device_action(16, address)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if stop and stop.is_set():
                return False
            time.sleep(1)
            if any(d['address'] == address and d['connected'] for d in self.devices()):
                return True
        raise RuntimeError('Headphones did not connect. Switch them on, bring them nearby, and try again.')

    def scan(self, mode=2, seconds=12, stop=None, update=lambda _: None):
        previous = self.byte(10)
        found = {}
        registered = False
        try:
            self.request(7, bytes([24]), feature=0)
            registered = True
            if mode == 2:
                self.set_pairing(0)
            self.set_pairing(mode)
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline and not (stop and stop.is_set()):
                response = decode(self.device.read(447, 250))
                if response:
                    self.notifications.append(response)
                while self.notifications:
                    _, command, data = self.notifications.pop(0)
                    if command != 129 or len(data) < 20:
                        continue
                    length = int.from_bytes(data[18:20], 'little')
                    if len(data) < 20 + length:
                        continue
                    address = data[9:15].hex(':')
                    entry = {'address': address, 'name': data[20:20 + length].decode('utf-8', errors='replace').rstrip('\x00'), 'connected': False}
                    if address not in found:
                        found[address] = entry
                        update(list(found.values()))
            return list(found.values())
        finally:
            try:
                self.set_pairing(previous)
            finally:
                if registered:
                    self.request(8, bytes([24]), feature=0)
