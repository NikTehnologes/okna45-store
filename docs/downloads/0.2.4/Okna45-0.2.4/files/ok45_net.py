"""Shared WiFi service: scan is a driver call, association is polled, secrets redacted."""
import network
import ok45_fs as fs
from ok45_kernel import ticks_ms, ticks_add, ticks_diff

CONFIG = '/wifi.json'


class WifiService:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.busy = False
        self.deadline = 0
        self.ssid = ''
        self.status = 'Ready'

    def credentials(self):
        value = fs.load_json(CONFIG, 2048, {'ssid': '', 'pass': ''})
        if not isinstance(value, dict):
            raise ValueError('Invalid WiFi configuration')
        self.validate(value.get('ssid', ''), value.get('pass', ''), empty=True)
        return {'ssid': value.get('ssid', ''), 'pass': value.get('pass', '')}

    @staticmethod
    def validate(ssid, password, empty=False):
        if (not isinstance(ssid, str) or (not empty and not ssid) or len(ssid.encode()) > 32 or
                any(ord(ch) < 32 for ch in ssid)):
            raise ValueError('SSID must be 1..32 bytes')
        if not isinstance(password, str) or len(password.encode()) > 64 or any(ord(ch) < 32 for ch in password):
            raise ValueError('Password limit is 64 bytes')

    def save(self, ssid, password):
        self.validate(ssid, password)
        fs.atomic_json(CONFIG, {'ssid': ssid, 'pass': password})
        self.status = 'Credentials saved'

    def scan(self):
        if self.busy:
            raise RuntimeError('Connecting; wait or turn WiFi off')
        self.wlan.active(True)
        seen, entries = set(), []
        # CYW43 scan() itself blocks; generators cannot preempt the hardware driver.
        for ssid, bssid, channel, rssi, auth, hidden in self.wlan.scan():
            try:
                name = ssid.decode('utf-8')
            except (UnicodeError, AttributeError):
                continue
            if not name or name in seen:
                continue
            seen.add(name)
            entries.append({'ssid': name, 'channel': channel, 'rssi': rssi, 'secure': bool(auth)})
            if len(entries) >= 32:
                break
        entries.sort(key=lambda entry: -entry['rssi'])
        self.status = 'Found %d networks' % len(entries)
        return entries

    def connect(self, ssid, password, timeout_ms=15000):
        self.validate(ssid, password)
        if self.busy:
            raise RuntimeError('Connection already in progress')
        self.wlan.active(True)
        self.wlan.disconnect()
        self.wlan.connect(ssid, password)
        self.ssid, self.busy = ssid, True
        self.deadline = ticks_add(ticks_ms(), max(1000, min(60000, timeout_ms)))
        self.status = 'Connecting...'

    def poll(self):
        if self.busy:
            code = self.wlan.status()
            if self.wlan.isconnected():
                self.busy = False
                self.status = 'Connected ' + self.wlan.ifconfig()[0]
            elif isinstance(code, int) and code < 0:
                self.busy = False
                self.wlan.disconnect()
                self.status = 'WiFi failed (%d)' % code
            elif ticks_diff(ticks_ms(), self.deadline) >= 0:
                self.busy = False
                self.wlan.disconnect()
                self.status = 'Connection timed out'
        return self.snapshot()

    def off(self):
        self.busy = False
        self.wlan.disconnect()
        self.wlan.active(False)
        self.status = 'WiFi off'

    def snapshot(self):
        connected = self.wlan.isconnected()
        ssid = self.ssid
        if connected and not ssid:
            try:
                ssid = self.wlan.config('ssid') or ''
            except (OSError, ValueError):
                pass
        return {'active': self.wlan.active(), 'connected': connected, 'connecting': self.busy,
                'ssid': ssid, 'ip': self.wlan.ifconfig()[0] if connected else None,
                'status': self.status}
