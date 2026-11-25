"""Load only open apps. Source blocks stay on flash; imports have scoped ownership."""
import gc
import sys

SOURCE = '/ok45_apps.py'
CLASSES = {'about': 'About', 'clock': 'Clock', 'monitor': 'Monitor', 'files': 'Files',
           'notes': 'Notes', 'tasks': 'Tasks', 'console': 'Console', 'cube': 'Cube'}
MODULES = {'wifi': ('ok45_wifi_app', 'Wifi'), 'store': ('ok45_store_app', 'Store'),
           'run_app': ('ok45_run_app', 'Run')}
SERVICES = ('ok45_script', 'ok45_net', 'ok45_pkg', 'ok45_store', 'ok45_update',
            'ok45_sin', 'ok45_tx', 'urequests', 'requests', 'ntptime')
NEEDS = {'run_app': ('ok45_run_app',),
         'wifi': ('ok45_wifi_app', 'ok45_net'),
         'store': ('ok45_store_app', 'ok45_store', 'ok45_sin')}


def group(kind):
    return 'console' if kind == 'packages' or kind.startswith('script:') else kind


class Loader:
    def __init__(self):
        self.classes = {}
        self.pinned = set(sys.modules)
        self.owned = {}

    def source(self, kind):
        if kind not in CLASSES:
            raise ValueError('Missing built-in source: ' + kind)
        marker = ('#@app ' + kind).encode()
        with open(SOURCE, 'rb') as file:
            while True:
                line = file.readline()
                if not line:
                    raise ValueError('Missing built-in source: ' + kind)
                if line.rstrip() == marker:
                    break
            start = file.tell()
            while True:
                end = file.tell()
                line = file.readline()
                if end - start > 32768 or not line:
                    raise ValueError('Invalid built-in source: ' + kind)
                if line.rstrip() == b'#@end':
                    break
            file.seek(start)
            return file.read(end - start).decode()

    def create(self, kind, desktop, window, path=None):
        key = group(kind)
        cls = self.classes.get(key)
        if cls is None:
            gc.collect()
            if key in MODULES:
                module, entry = MODULES[key]
                cls = getattr(__import__(module), entry)
            else:
                namespace = {'__name__': 'ok45_builtin_' + key, '__file__': SOURCE,
                             '__zerobook_guest__': True}
                exec(self.source(key), namespace)
                cls = namespace[CLASSES[key]]
            self.classes[key] = cls
        if path is not None and key in ('notes', 'store', 'run_app', 'console'):
            return cls(desktop, window, path=path)
        return cls(desktop, window)

    def prune(self, windows):
        live = set(group(window.kind) for window in windows if window.app is not None)
        changed = False
        for key in tuple(self.classes):
            if key not in live:
                del self.classes[key]
                changed = True
        # Opaque user apps and in-flight jobs may retain/import service modules.
        busy = any(window.app is not None and ((group(window.kind) not in CLASSES and
                   window.kind not in MODULES) or getattr(window.app, 'running', False) or
                   getattr(window.app, 'busy', False)) for window in windows)
        needed = set()
        for key in live:
            needed.update(NEEDS.get(key, ()))
        for name in SERVICES + tuple(item[0] for item in MODULES.values()):
            module = sys.modules.get(name)
            if module is not None and name not in self.pinned and name not in self.owned:
                self.owned[name] = module
        if not busy:
            for name in tuple(self.owned):
                if name not in needed:
                    module = self.owned.pop(name)
                    if sys.modules.get(name) is module:
                        del sys.modules[name]
                    else:
                        self.pinned.add(name)
                    changed = True
        if changed:
            gc.collect()
