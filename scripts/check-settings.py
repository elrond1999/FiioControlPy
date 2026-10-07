"""Hardware round-trip check; restore all initial values even on failure."""
from bt11 import BT11

with BT11() as device:
    before = device.snapshot()
    try:
        device.set_name(before['name'])
        device.set_brightness((before['brightness'] + 1) % 8)
        assert device.byte(82) == (before['brightness'] + 1) % 8
        device.set_codecs(before['codecs'], before['ldac_mode'], before['aptx_mode'])
        device.set_pairing(before['pairing_mode'])
    finally:
        device.set_brightness(before['brightness'])
    after = device.snapshot()
    for key in ('name', 'brightness', 'codecs', 'ldac_mode', 'aptx_mode', 'pairing_mode'):
        assert before[key] == after[key], (key, before[key], after[key])
    print('Name, brightness, codecs, quality modes and pairing-mode write/read checks passed.')
    print('Original settings preserved.')
