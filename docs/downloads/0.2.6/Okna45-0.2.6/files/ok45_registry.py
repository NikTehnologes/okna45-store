"""Bounded launcher metadata. Installed programs are registered by packages."""
import ok45_fs as fs
from ok45_api import API_VERSION, Context

DATABASE = '/system/pkg/installed.json'
CATEGORIES = ('Tools', 'System', 'Network', 'Games', 'Apps')
MAX_APPS = 32
DEFAULT_ICON = ('..####..', '.######.', '.#....#.', '.#.##.#.', '.#.##.#.', '.#....#.', '.######.', '..####..')
ICONS = {
    'notes': ('..####..', '..#..##.', '..#...#.', '..###.#.', '..#...#.', '..###.#.', '..#...#.', '..#####.'),
    'files': ('........', '.###....', '.#..###.', '.######.', '.#....#.', '.#....#.', '.######.', '........'),
    'console': ('........', '.######.', '.#....#.', '.#.#..#.', '.#..#.#.', '.#.#..#.', '.######.', '........'),
    'clock': ('..####..', '.#....#.', '#...#..#', '#...#..#', '#...##.#', '#......#', '.#....#.', '..####..'),
    'wifi': ('........', '..####..', '.#....#.', '#.####.#', '..#..#..', '...##...', '........', '...##...'),
    'cube': ('...##...', '.##..##.', '#..##..#', '#...#..#', '#...#..#', '#..##..#', '.##..##.', '...##...'),
    'system': ('...##...', '.#.#..#.', '..####..', '###..###', '###..###', '..####..', '.#..#.#.', '...##...')}
BUILTINS = (('about', 'Welcome', 'Tools', 'system'), ('notes', 'Notes', 'Tools', 'notes'),
            ('console', 'Console', 'Tools', 'console'), ('files', 'Files', 'Tools', 'files'),
            ('clock', 'Clock', 'Tools', 'clock'), ('monitor', 'Monitor', 'System', 'system'),
            ('tasks', 'Tasks', 'System', 'system'), ('packages', 'Packages', 'System', 'files'),
            ('wifi', 'WiFi', 'Network', 'wifi'), ('cube', 'Cube', 'Games', 'cube'),
            ('run_app', 'Run', 'Tools', 'console'), ('store', 'Store', 'System', 'files'))


def validate_desktop(value, package):
    if not isinstance(value, dict):
        raise ValueError('Invalid desktop application metadata')
    title = value.get('title', package['name'])
    if not isinstance(title, str) or not 1 <= len(title) <= 28 or any(not 32 <= ord(ch) <= 126 for ch in title):
        raise ValueError('Application title must be 1..28 ASCII characters')
    if value.get('category', 'Apps') not in CATEGORIES:
        raise ValueError('Unknown application category')
    kind = value.get('type', 'window')
    if kind not in ('window', 'terminal'):
        raise ValueError('Application type must be window or terminal')
    entry = value.get('entry', package['name'] + '.py')
    paths = [item['path'] for item in package['files']]
    if entry not in paths or not entry.endswith('.py'):
        raise ValueError('Desktop entry must be a Python file owned by this package')
    if kind == 'terminal' and entry != package['name'] + '.py':
        raise ValueError('Terminal launcher requires NAME.py at flash root')
    if value.get('mode', 'auto') not in ('auto', 'terminal', 'gfx'):
        raise ValueError('Terminal display mode must be auto, terminal or gfx')
    api = value.get('api', 1)
    if isinstance(api, bool) or api != API_VERSION:
        raise ValueError('Unsupported application API version')
    cls = value.get('class', 'Main')
    if (not isinstance(cls, str) or not 1 <= len(cls) <= 32 or
            any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for ch in cls) or
            '0' <= cls[0] <= '9'):
        raise ValueError('Invalid application class')
    size = value.get('size', [264, 172])
    if (not isinstance(size, (list, tuple)) or len(size) != 2 or
            any(isinstance(n, bool) or not isinstance(n, int) for n in size) or
            not 160 <= size[0] <= 312 or not 100 <= size[1] <= 196):
        raise ValueError('Application window size outside 160..312 x 100..196')
    if not isinstance(value.get('singleton', True), bool):
        raise ValueError('singleton must be boolean')
    icon = value.get('icon', DEFAULT_ICON)
    if (not isinstance(icon, (list, tuple)) or len(icon) not in (8, 16) or
            any(not isinstance(row, str) or len(row) != len(icon) or
                any(ch not in '.#+' for ch in row) for row in icon)):
        raise ValueError('Icon must be 8x8 or 16x16 rows of . # +')
    return value


class Registry:
    def __init__(self):
        self.items, self.errors, self.version = [], [], 0
        self.reload()

    def reload(self):
        self.errors = []
        items = [{'id': identity, 'title': title, 'category': category, 'type': 'builtin',
                  'icon': ICONS.get(icon, DEFAULT_ICON), 'package': None,
                  'singleton': identity != 'notes'} for identity, title, category, icon in BUILTINS]
        try:
            installed = fs.load_json(DATABASE, 32768, {'packages': {}})['packages']
            if not isinstance(installed, dict) or len(installed) > MAX_APPS:
                raise ValueError('Invalid application database')
            for name in sorted(installed):
                try:
                    record = installed[name]
                    if not isinstance(record, dict):
                        raise ValueError('Invalid installed application record')
                    package = dict(record, name=name)
                    desktop = record.get('desktop')
                    if desktop is None:
                        if not any(item['path'] == name + '.py' for item in record['files']):
                            continue  # Data-only dependency has no runnable icon.
                        desktop = {'type': 'terminal', 'title': name, 'entry': name + '.py'}
                    validate_desktop(desktop, package)
                    if any(item['id'] == name for item in items):
                        raise ValueError('Application ID is reserved')
                    items.append({'id': name, 'title': desktop.get('title', name),
                                  'category': desktop.get('category', 'Apps'),
                                  'type': desktop.get('type', 'window'), 'package': name,
                                  'version': record['version'], 'entry': desktop.get('entry', name + '.py'),
                                   'class': desktop.get('class', 'Main'), 'api': API_VERSION,
                                   'mode': desktop.get('mode', 'auto'),
                                  'size': desktop.get('size', [264, 172]),
                                  'singleton': desktop.get('singleton', True),
                                  'icon': desktop.get('icon', DEFAULT_ICON)})
                except (ValueError, KeyError, TypeError) as error:
                    self.errors.append('%s: %s' % (name, error))
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.errors.append(str(error))
        self.items = items
        self.version += 1

    def get(self, identity):
        for item in self.items:
            if item['id'] == identity:
                return item
        return None

    def category(self, name):
        return [item for item in self.items if item['category'] == name]

    def snapshot(self):
        return [dict(item) for item in self.items]

    def create(self, record, desktop, window):
        namespace = {'__name__': 'ok45_app_' + record['id'], '__file__': '/' + record['entry'],
                     '__zerobook_guest__': True}
        exec(fs.read_text('/' + record['entry'], 32768), namespace)
        cls = namespace.get(record['class'])
        if not callable(cls):
            raise ValueError('Application entry has no ' + record['class'])
        app = cls(Context(desktop, window, record['id'], record['package']), window)
        for method in ('draw', 'key', 'tick', 'close', 'controls', 'click', 'semantic', 'invalidate', 'moved'):
            if not callable(getattr(app, method, None)):
                raise ValueError('Application must implement ' + method)
        return app
