"""Small graphical launcher for built-ins, installed apps and editor scripts."""
from ok45_api import Application
from ok45_ui import WHITE, LIGHT


class Run(Application):
    title = 'Run'
    def __init__(self, desktop, window, path=None):
        super().__init__(desktop, window)
        self.value = path or ''
        self.mode = 'auto'
        self.status = 'App ID, command or /script.py'

    def key(self, code):
        if code in (8, 127):
            self.value = self.value[:-1]
        elif code in (10, 13):
            self.activate({'action': 'run'})
        elif 32 <= code <= 126 and len(self.value) < 160:
            self.value += chr(code)
        self.invalidate()

    def controls(self):
        x, y, w, h = self.window.client()
        label = {'auto': 'Auto', 'window': 'Window', 'terminal': 'Text', 'gfx': 'Full'}[self.mode]
        controls = self.toolbar((('run', 'Run'), ('mode', label), ('edit', 'Edit')))
        controls.append({'action': 'input', 'label': 'Command', 'button': False,
                         'rect': [x + 4, y + 18, w - 8, 22]})
        return controls

    def activate(self, control):
        action = control['action']
        try:
            if action == 'input':
                self.desktop.set_mode('input')
            elif action == 'mode':
                modes = ('auto', 'window', 'terminal', 'gfx')
                self.mode = modes[(modes.index(self.mode) + 1) % len(modes)]
            elif action == 'edit':
                path = self.value.strip().split()[0] if self.value.strip() else '/scripts/new.py'
                self.desktop.open('notes', path=path)
            else:
                window = self.desktop.launch(self.value, self.mode)
                self.status = self.desktop.status if window is None else 'Opened ' + window.title
                self.desktop.set_mode('pointer')
        except Exception as error:
            self.status = str(error)
        self.invalidate()

    def semantic(self):
        return {'command': self.value, 'mode': self.mode, 'status': self.status,
                'lines': ['App ID / command / file.py', self.value, 'Mode: ' + self.mode,
                          'Editor scripts: /scripts/', self.status]}

    def draw(self, canvas, rect):
        x, y, w, h = rect
        columns = max(1, (w - 14) // 8)
        canvas.fill(rect, LIGHT)
        canvas.text(x + 4, y + 4, 'App ID / command / file.py'[:columns])
        canvas.fill((x + 4, y + 18, w - 8, 22), WHITE)
        canvas.bevel((x + 4, y + 18, w - 8, 22), False)
        canvas.text(x + 7, y + 25, (self.value + '_')[-columns:])
        canvas.text(x + 4, y + 48, ('Mode: ' + self.mode)[:columns])
        canvas.text(x + 4, y + 64, 'Own scripts: /scripts/'[:columns])
        canvas.text(x + 4, y + h - 33, self.status[:columns])
        self.draw_controls(canvas)
