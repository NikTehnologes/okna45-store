"""CardKB GUI for WiFi; passwords never enter semantic observations."""
from ok45_api import Application, UP, DOWN, ENTER, BACKSPACE, DELETE
from ok45_net import WifiService
from ok45_ui import BLACK, WHITE, NAVY, SHADOW, SILVER, contains


class Wifi(Application):
    title = 'WiFi'
    interval_ms = 100

    def __init__(self, desktop, window):
        super().__init__(desktop, window)
        self.service = WifiService()
        self.ssid, self.password = '', ''
        self.field = 'ssid'
        self.networks, self.selected, self.scroll = [], 0, 0
        self.last = None
        try:
            value = self.service.credentials()
            self.ssid, self.password = value['ssid'], value['pass']
        except Exception as error:
            self.service.status = str(error)

    def rows(self):
        return max(1, (self.window.client()[3] - 94) // 12)

    def choose(self, index):
        if self.networks:
            self.selected = max(0, min(len(self.networks) - 1, index))
            self.ssid = self.networks[self.selected]['ssid']
            self.scroll = min(self.scroll, self.selected)
            if self.selected >= self.scroll + self.rows():
                self.scroll = self.selected - self.rows() + 1
        self.invalidate()

    def controls(self):
        x, y, w, h = self.window.client()
        controls = self.toolbar((('scan', 'Scan'), ('save', 'Save'), ('connect', 'Link'), ('off', 'Off')))
        controls[0]['enabled'] = not self.service.busy
        controls[1]['enabled'] = bool(self.ssid)
        controls[2]['enabled'] = bool(self.ssid) and not self.service.busy
        controls.extend([{'action': 'ssid', 'label': 'SSID', 'rect': [x + 2, y + 2, w - 4, 20], 'button': False},
                         {'action': 'password', 'label': 'Password', 'rect': [x + 2, y + 25, w - 4, 20], 'button': False}])
        controls.extend({'action': 'select', 'label': entry['ssid'], 'index': self.scroll + row,
                         'rect': [x + 2, y + 49 + row * 12, w - 4, 12], 'button': False}
                        for row, entry in enumerate(self.networks[self.scroll:self.scroll + self.rows()]))
        return controls

    def activate(self, control):
        action = control['action']
        try:
            if action in ('ssid', 'password'):
                self.field = action
                self.desktop.set_mode('input')
            elif action == 'select':
                self.choose(control['index'])
            elif action == 'scan':
                self.networks = self.service.scan()
                self.selected = self.scroll = 0
            elif action == 'save':
                self.service.save(self.ssid, self.password)
            elif action == 'connect':
                self.service.connect(self.ssid, self.password)
            elif action == 'off':
                self.service.off()
        except Exception as error:
            self.service.status = str(error)
        self.invalidate()

    def key(self, code):
        if code in (UP, DOWN):
            self.choose(self.selected + (-1 if code == UP else 1))
        elif code == ENTER:
            if self.field == 'ssid':
                self.field = 'password'
            else:
                self.desktop.set_mode('pointer')
        elif code in (BACKSPACE, DELETE):
            setattr(self, self.field, getattr(self, self.field)[:-1])
        elif 32 <= code <= 126:
            value = getattr(self, self.field)
            if len(value.encode()) < (32 if self.field == 'ssid' else 64):
                setattr(self, self.field, value + chr(code))
        self.invalidate()

    def tick(self):
        value = self.service.poll()
        if value != self.last:
            self.last = value
            self.invalidate()
        return False

    def close(self):
        if self.service.busy:
            self.service.off()
        return True

    def semantic(self):
        value = self.service.snapshot()
        # No password or credentials dictionary in /desktop, text or screenshots.
        return {'wifi': value, 'ssid': self.ssid, 'password_length': len(self.password),
                'field': self.field, 'networks': self.networks, 'selected': self.selected,
                'scroll': self.scroll, 'status': value['status'],
                'lines': ['SSID: ' + self.ssid, 'Password: ' + '*' * min(16, len(self.password)),
                          value['status']]}

    def draw(self, canvas, rect):
        canvas.fill(rect, WHITE)
        x, y, w, h = rect
        for index, field in enumerate(('ssid', 'password')):
            fy = y + 2 + index * 23
            canvas.fill((x + 2, fy, w - 4, 20), SILVER)
            canvas.bevel((x + 2, fy, w - 4, 20), False)
            value = self.ssid if field == 'ssid' else '*' * len(self.password)
            label = ('SSID: ' if field == 'ssid' else 'Key: ') + value
            if self.field == field and self.desktop.wm.input_mode == 'input':
                label += '_'
            canvas.text(x + 5, fy + 6, label[-max(1, (w - 10) // 8):], BLACK)
        for row, entry in enumerate(self.networks[self.scroll:self.scroll + self.rows()]):
            selected = self.scroll + row == self.selected
            ry = y + 49 + row * 12
            canvas.fill((x + 2, ry, w - 4, 12), NAVY if selected else WHITE)
            label = '%s %d%s' % (entry['ssid'][:max(1, (w - 64) // 8)], entry['rssi'], '*' if entry['secure'] else '')
            canvas.text(x + 4, ry + 2, label[:(w - 8) // 8], WHITE if selected else SHADOW)
        canvas.text(x + 3, y + h - 34, self.service.status[:(w - 6) // 8], BLACK)
        self.draw_controls(canvas)
