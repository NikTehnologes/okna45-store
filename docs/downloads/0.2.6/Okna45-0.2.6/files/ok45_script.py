"""Trusted user scripts: lightweight protection, graphical output and API windows."""
import ok45_fs as fs
import gc

MAX_SCRIPT = 32768
PROTECTED = ('main', 'boot', 'desktop', 'run', 'apt', 'install', 'update', 'updates',
             'ps', 'kill', 'timezone', 'edit', 'clock', 'wifi', 'sysmon', 'web', 'help',
             'demo_3d', 'demo_gfx', 'demo_text', 'weather', 'info', 'dir', 'clear', 'df',
             'pwd', 'reboot', 'copy', 'del', 'md', 'ren', 'led', 'type', 'curl', 'publish',
             'ili9341', 'sdcard', 'xpt2046', 'setup', 'setup2', 'NotMain')


def file_path(value):
    if not isinstance(value, str):
        raise ValueError('Use an absolute file path')
    path = value if value.startswith('/') else '/' + value
    if (not 2 <= len(path) <= 100 or
            any(part in ('', '.', '..') for part in path[1:].split('/')) or
            any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-' for ch in path)):
        raise ValueError('Use /folder/name.py or /folder/name.txt; no spaces or ..')
    return path


def editable(path):
    path = file_path(path)
    if (any(path.startswith(prefix) for prefix in ('/system/', '/repo/', '/apps/')) or
            path.endswith('.mpy') or path.endswith('.sin')):
        return False
    if path.endswith('.py') and '/' not in path[1:]:
        return path[1:-3] not in PROTECTED and not path[1:].startswith('ok45_')
    return True


def source(path):
    path = file_path(path)
    if not path.endswith('.py'):
        raise ValueError('Only .py source scripts can be run')
    return fs.read_text(path, MAX_SCRIPT)


def kind(path, text=None):
    """Auto is a small source hint, not a Python parser; Run can override it."""
    text = source(path) if text is None else text
    start = 0
    while start <= len(text):
        end = text.find('\n', start)
        if end < 0:
            end = len(text)
        line = text[start:end]
        start = end + 1
        compact = line.strip().replace(' ', '')
        if compact.startswith('classMain(') and 'ok45_api' in text:
            return 'window'
        if compact in ("MODE='gfx'", 'MODE="gfx"'):
            return 'gfx'
    return 'terminal'


def namespace(path, term=None, args=None):
    scope = {'__name__': 'ok45_user_script', '__file__': file_path(path),
             '__zerobook_guest__': True, 'term': term, 'args': args or []}
    if term is not None:
        def output(*values, **options):
            separator, end = options.get('sep', ' '), options.get('end', '\n')
            target = options.get('file', term)
            writer = getattr(target, 'write_stream', target.write)
            writer(separator.join(str(value) for value in values) + end)
        scope['print'] = output
        if hasattr(term, 'input_line'):
            def input_line(prompt=''):
                result = term.input_line(prompt)
                if result is None:
                    raise EOFError('Input cancelled')
                return result
            scope['input'] = input_line
    return scope


def run_file(path, term, args=None):
    job = run_job(path, term, args)
    try:
        for delay in job:
            if delay:
                import time
                getattr(time, 'sleep_ms', lambda ms: time.sleep(ms / 1000))(delay)
    finally:
        job.close()


def run_job(path, term, args=None):
    """Plain Python runs once; generator run(term,args) yields cooperative delays."""
    scope = text = entry = result = None
    gc.collect()
    try:
        text = source(path)
        scope = namespace(path, term, args)
        if not text.startswith('def run(') and not text.startswith('def run (') and '\ndef run(' not in text and '\ndef run (' not in text:
            scope['__name__'] = '__main__'
        exec(text, scope)
        text = None
        entry = scope.get('run')
        result = entry(term, args or []) if callable(entry) else None
        if hasattr(result, '__next__'):
            yield from result
    finally:
        try:
            if hasattr(result, 'close'):
                result.close()
        finally:
            if scope is not None:
                scope.clear()
            scope = text = entry = result = None
            gc.collect()


def window_app(path, desktop, window, args=None):
    from ok45_api import Application, Context
    scope = namespace(path, args=args)
    exec(source(path), scope)
    entry = scope.get('Main')
    if not callable(entry):
        raise ValueError('Window script must define Main(Application)')
    identity = 'script_' + file_path(path)[1:-3].replace('/', '_')
    context = Context(desktop, window, identity)
    context.args = args or []
    app = entry(context, window)
    if not isinstance(app, Application):
        raise ValueError('Main must extend ok45_api.Application')
    window.title = str(getattr(app, 'title', path.rsplit('/', 1)[-1]))[:28]
    return app
