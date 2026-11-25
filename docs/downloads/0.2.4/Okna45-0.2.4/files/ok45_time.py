"""UTC RTC + persistent fixed UTC offsets. No host timezone or implicit DST."""
import time
import ok45_fs as fs

CONFIG = '/system/timezone.json'
PRESETS = (('UTC', 0), ('Europe/Moscow', 180), ('Asia/Yekaterinburg', 300),
           ('Asia/Kolkata', 330), ('Asia/Kathmandu', 345), ('Asia/Tokyo', 540),
           ('UTC-05:00', -300), ('UTC+14:00', 840))
_settings = None


def offset_text(minutes):
    return 'UTC%s%02d:%02d' % ('+' if minutes >= 0 else '-', abs(minutes) // 60, abs(minutes) % 60)


def _validate(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid timezone settings')
    minutes = value.get('offset_minutes')
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not -720 <= minutes <= 840:
        raise ValueError('UTC offset must be -12:00..+14:00')
    label = value.get('label', offset_text(minutes))
    if not isinstance(label, str) or len(label) > 32 or any(not 32 <= ord(ch) <= 126 for ch in label):
        raise ValueError('Invalid timezone label')
    return {'offset_minutes': minutes, 'label': label, 'dst': False, 'rtc': 'UTC'}


def settings():
    global _settings
    if _settings is None:
        _settings = _validate(fs.load_json(CONFIG, 1024, {'offset_minutes': 0, 'label': 'UTC'}))
    return dict(_settings)


def set_timezone(value, label=None):
    global _settings
    if isinstance(value, str):
        presets = dict(PRESETS)
        if value in presets:
            label, value = value, presets[value]
        else:
            text = value[3:] if value.startswith('UTC') else value
            if (len(text) != 6 or text[0] not in '+-' or text[3] != ':' or
                    any(ch not in '0123456789' for ch in text[1:3] + text[4:]) or int(text[4:]) >= 60):
                raise ValueError('Use UTC, a preset, or +HH:MM / -HH:MM')
            value = (int(text[1:3]) * 60 + int(text[4:])) * (-1 if text[0] == '-' else 1)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('UTC offset must be integer minutes')
    selected = _validate({'offset_minutes': value, 'label': label or offset_text(value)})
    fs.atomic_json(CONFIG, selected)
    _settings = selected
    return dict(selected)


def localtime(seconds=None):
    stamp = time.time() if seconds is None else seconds
    return time.gmtime(stamp + settings()['offset_minutes'] * 60)


def sync():
    import network
    if not network.WLAN(network.STA_IF).isconnected():
        raise OSError('Connect WiFi before NTP sync')
    import ntptime
    ntptime.settime()  # Keep RTC in UTC; offsets are applied only for presentation.
