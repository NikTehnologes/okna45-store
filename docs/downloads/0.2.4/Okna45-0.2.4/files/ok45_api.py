"""Okna45 application API v1. Trusted apps share the MicroPython interpreter."""
from ok45_ui import BLACK, WHITE, LIGHT, SILVER, SHADOW, NAVY, GREEN, TEAL, WIDTH, HEIGHT, rgb, contains
from ok45_kernel import ticks_ms, ticks_diff, ticks_add

API_VERSION = 1
ENTER, ESC, TAB, BACKSPACE, DELETE = 13, 27, 9, 8, 127
LEFT, UP, DOWN, RIGHT = 180, 181, 182, 183


def _relative(path):
    if (not isinstance(path, str) or not path or len(path) > 96 or
            path.startswith('/') or '\\' in path or
            any(part in ('', '.', '..') for part in path.split('/')) or
            any(ord(ch) < 32 or ord(ch) > 126 for ch in path)):
        raise ValueError('Use a relative application data path')
    return path


class Context:
    """Convenience and lifecycle boundary, NOT a security sandbox."""
    def __init__(self, desktop, window, app_id, package=None):
        self.desktop, self.window = desktop, window
        self.app_id, self.package = app_id, package

    def data_path(self, relative='settings.json'):
        return '/data/' + (self.package or self.app_id) + '/' + _relative(relative)

    def read_text(self, relative, default='', limit=8192):
        import ok45_fs as fs
        path = self.data_path(relative)
        return fs.read_text(path, min(8192, max(1, limit))) if fs.exists(path) else default

    def save_text(self, relative, text):
        import ok45_fs as fs
        if len(text.encode('utf-8')) > 8192:
            raise ValueError('Application data limit is 8192 bytes')
        fs.atomic_text(self.data_path(relative), text)

    def load_json(self, relative='settings.json', default=None):
        import ok45_fs as fs
        return fs.load_json(self.data_path(relative), 8192, default)

    def save_json(self, value, relative='settings.json'):
        import json
        self.save_text(relative, json.dumps(value))

    def spawn(self, name, iterator):
        return self.desktop.scheduler.spawn(name, iterator, owner=self.window.id)

    def pause(self, task_id, paused=True):
        task = self.desktop.scheduler.find(task_id)
        return bool(task and task.owner == self.window.id and
                    self.desktop.scheduler.pause(task_id, paused))

    def cancel(self, task_id):
        task = self.desktop.scheduler.find(task_id)
        return bool(task and task.owner == self.window.id and
                    self.desktop.scheduler.cancel(task_id))

    def launch(self, app_id, **options):
        return self.desktop.open(app_id, **options)

    def applications(self):
        return self.desktop.registry.snapshot()

    def input(self, enabled=True):
        self.desktop.wm.focus(self.window.id)
        self.desktop.set_mode('input' if enabled else 'pointer')

    def status(self, text):
        self.desktop.status = str(text)[:160]
        self.desktop.changed()

    def localtime(self, seconds=None):
        import ok45_time
        return ok45_time.localtime(seconds)

    def timezone(self):
        import ok45_time
        return ok45_time.settings()

    def network(self):
        from ok45_net import WifiService
        return WifiService()


class Application:
    """Subclass as Main(context, window); all drawing goes through Canvas."""
    title = 'App'
    interval_ms = 1000

    def __init__(self, context, window):
        self.context, self.window = context, window
        # Existing bundled apps use a Desktop directly; API apps get Context.
        self.desktop = getattr(context, 'desktop', context)

    def invalidate(self, rect=None):
        self.desktop.wm.invalidate(self.window, rect)

    def close(self):
        return True

    def key(self, code):
        pass

    def tick(self):
        return False

    def moved(self, dx, dy):
        self.invalidate()

    def mode_changed(self):
        self.invalidate()

    def controls(self):
        return []

    def toolbar(self, items):
        if not items:
            return []
        x, y, w, h = self.window.client()
        width = (w - 4 - 3 * (len(items) - 1)) // len(items)
        return [{'action': action, 'label': label, 'enabled': True,
                 'rect': [x + 2 + index * (width + 3), y + h - 20, width, 18]}
                for index, (action, label) in enumerate(items)]

    def activate(self, control):
        pass

    def click(self, x, y):
        for control in self.controls():
            if contains(control['rect'], x, y):
                if control.get('enabled', True):
                    self.activate(control)
                return True
        return False

    def draw_controls(self, canvas):
        if canvas.clip is None:
            return
        for control in self.controls():
            if control.get('button', True):
                canvas.button(control['rect'], control['label'],
                              selected=control.get('selected', False),
                              enabled=control.get('enabled', True))

    def semantic(self):
        return {'lines': []}

    def draw(self, canvas, rect):
        canvas.fill(rect, LIGHT)
        x, y, w, h = rect
        rows = (h - 24) // 10 if self.controls() else h // 10
        for row, line in enumerate(self.semantic().get('lines', [])[:max(0, rows)]):
            canvas.text(x + 4, y + 4 + row * 10, str(line)[:max(0, (w - 8) // 8)], BLACK)
        self.draw_controls(canvas)
