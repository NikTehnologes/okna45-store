"""apt-like trusted-source packages, bounded downloads and recoverable installs.

    Package hashes detect corrupt bytes, not a malicious repository. Only add
    trusted sources. Package Python executes with the same privileges as OS.
"""
import json
import hashlib
import binascii
import gc
import ok45_fs as fs
from ok45_sin import Bundle, file_hash, version_key, safe_relative
from ok45_registry import validate_desktop, BUILTINS

ROOT = '/system/pkg'
SOURCE = ROOT + '/source.json'
INDEX = ROOT + '/index.json'
DATABASE = ROOT + '/installed.json'
JOURNAL = ROOT + '/journal.json'
STAGE = ROOT + '/stage'
DEFAULT_SOURCE = 'https://niktehnologes.github.io/okna45-store/index.json'
MAX_INDEX = 16384
MAX_FILE = 32768
MAX_TOTAL = 65536
MAX_PACKAGES = 32
CORE = {'main', 'boot', 'ili9341', 'sdcard', 'xpt2046', 'setup', 'setup2',
        'desktop', 'apt', 'ps', 'kill', 'ok45_kernel', 'ok45_ui', 'ok45_apps',
        'ok45_desktop', 'ok45_pkg', 'ok45_fs', 'ok45_boot', 'ok45_api', 'ok45_registry',
        'ok45_time', 'ok45_net', 'ok45_wifi_app', 'ok45_tx', 'ok45_sin', 'ok45_update',
        'install', 'update', 'updates', 'timezone', 'publish', 'ok45_script', 'ok45_store',
        'ok45_run_app', 'ok45_store_app', 'edit', 'clock', 'wifi', 'sysmon', 'web', 'help',
        'run', 'demo_3d', 'demo_gfx', 'demo_text', 'weather', 'info', 'dir', 'clear', 'df',
        'pwd', 'reboot', 'copy', 'del', 'md', 'ren', 'led', 'type', 'curl'}
CORE.update(item[0] for item in BUILTINS)
_busy = False


def name_ok(name):
    return (isinstance(name, str) and 1 <= len(name) <= 32 and 'a' <= name[0] <= 'z' and
             all('a' <= ch <= 'z' or '0' <= ch <= '9' or ch == '_' for ch in name))


def protected_name(name):
    return name in CORE or name.startswith('ok45_')


def validate_index(index):
    if not isinstance(index, dict) or isinstance(index.get('format'), bool) or index.get('format') != 1:
        raise ValueError('Repository format must be 1')
    packages = index.get('packages')
    if not isinstance(packages, list) or len(packages) > MAX_PACKAGES:
        raise ValueError('Repository package limit is %d' % MAX_PACKAGES)
    seen, paths = set(), set()
    for package in packages:
        if not isinstance(package, dict) or not name_ok(package.get('name')):
            raise ValueError('Invalid package name')
        name = package['name']
        if name in seen or protected_name(name):
            raise ValueError('Duplicate or protected package: ' + name)
        seen.add(name)
        version_key(package.get('version'))
        summary = package.get('summary', '')
        if not isinstance(summary, str) or len(summary) > 160:
            raise ValueError('Invalid package summary')
        depends = package.get('depends', [])
        if not isinstance(depends, list) or len(depends) > 8 or not all(name_ok(dep) for dep in depends):
            raise ValueError('Invalid dependencies')
        files = package.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= 8:
            raise ValueError('Package requires 1..8 files')
        total = 0
        for item in files:
            if not isinstance(item, dict):
                raise ValueError('Invalid file entry')
            path, source = item.get('path'), item.get('source')
            if not safe_relative(path) or not safe_relative(source):
                raise ValueError('Unsafe package file path')
            if '/' not in path:
                module = path[:-3] if path.endswith('.py') else ''
                if not name_ok(module) or protected_name(module):
                    raise ValueError('Only non-core Python modules may be installed at flash root')
            elif not path.startswith('apps/' + name + '/'):
                raise ValueError('Package data must be inside apps/' + name)
            if path in paths:
                raise ValueError('Multiple packages own ' + path)
            paths.add(path)
            size, digest = item.get('size'), item.get('sha256')
            if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_FILE:
                raise ValueError('Package file size must be 1..%d bytes' % MAX_FILE)
            if (not isinstance(digest, str) or len(digest) != 64 or
                    any(ch not in '0123456789abcdef' for ch in digest)):
                raise ValueError('SHA256 is required for every file')
            total += size
        if total > MAX_TOTAL:
            raise ValueError('Package exceeds transaction byte budget')
        if 'desktop' in package:
            validate_desktop(package['desktop'], package)
    return index


def _digest(hasher):
    return binascii.hexlify(hasher.digest()).decode()


def _join(source, relative):
    return source.rsplit('/', 1)[0] + '/' + relative


class PackageManager:
    def __init__(self):
        self._tx = None
        self.recover()

    @property
    def tx(self):
        if self._tx is None:
            from ok45_tx import Transaction
            self._tx = Transaction(ROOT, DATABASE)
        return self._tx

    def source(self):
        config = fs.load_json(SOURCE, 1024, {'url': DEFAULT_SOURCE})
        return config['url']

    def set_source(self, value):
        if _busy or fs._operation is not None:
            raise RuntimeError('Another package/update operation is active')
        if (not isinstance(value, str) or len(value) > 512 or
                not (value.startswith('/') or value.startswith('https://') or value.startswith('http://')) or
                '\\' in value or any(part == '..' for part in value.split('/'))):
            raise ValueError('Use an absolute local path or a trusted http(s) URL')
        fs.atomic_json(SOURCE, {'url': value})

    def installed(self):
        value = fs.load_json(DATABASE, MAX_INDEX, {'packages': {}})
        if not isinstance(value, dict) or not isinstance(value.get('packages'), dict):
            raise ValueError('Installed database is damaged')
        return value

    def index(self):
        index = fs.load_json(INDEX, MAX_INDEX)
        if index is None:
            raise ValueError('No cached index; run apt update')
        return validate_index(index)

    def _reader(self, source):
        if source.startswith('/'):
            return open(source, 'rb'), None
        gc.collect()
        import urequests
        gc.collect()
        response = urequests.get(source, timeout=10, stream=True)
        if response.status_code != 200:
            response.close()
            raise OSError('Repository HTTP %d' % response.status_code)
        if not hasattr(response, 'raw'):
            response.close()
            raise RuntimeError('urequests streaming response required')
        return response.raw, response

    def update_job(self):
        global _busy
        if _busy:
            raise RuntimeError('Another package operation is active')
        fs.acquire('apt')
        _busy = True
        temporary = INDEX + '.part'
        try:
            source = self.source()
            yield 'Reading ' + source
            reader, response = self._reader(source)
            try:
                yield from fs.receive_job(reader, temporary, MAX_INDEX)
            finally:
                response.close() if response else reader.close()
            reader, response = None, None
            gc.collect()
            index = validate_index(fs.load_json(temporary, MAX_INDEX))
            fs.remove(temporary)
            # Pin source together with cached metadata: source changes require update.
            index['source'] = source
            fs.atomic_json(INDEX, index, MAX_INDEX)
            yield 'Index: %d packages' % len(index['packages'])
        finally:
            _busy = False
            try:
                fs.remove(temporary)
            finally:
                fs.release('apt')

    def plan(self, names, index=None):
        index = self.index() if index is None else index
        catalog = {package['name']: package for package in index['packages']}
        installed = self.installed()['packages']
        visited, visiting, plan = set(), set(), []

        def visit(name):
            if name in visited:
                return
            if name in visiting:
                raise ValueError('Dependency cycle: ' + name)
            if name not in catalog:
                if name in installed:
                    visited.add(name)
                    return
                raise ValueError('Package not found: ' + name)
            visiting.add(name)
            package = catalog[name]
            for dependency in package.get('depends', []):
                visit(dependency)
            visiting.remove(name)
            visited.add(name)
            current = installed.get(name)
            if len(visited) > MAX_PACKAGES:
                raise ValueError('Installed package limit is %d' % MAX_PACKAGES)
            if current is None or version_key(package['version']) > version_key(current['version']):
                plan.append(package)

        for name in names:
            if not name_ok(name):
                raise ValueError('Invalid package name')
            visit(name)
        if sum(item['size'] for package in plan for item in package['files']) > MAX_TOTAL:
            raise ValueError('Transaction exceeds %d bytes; install in smaller batches' % MAX_TOTAL)
        return index, plan

    def _cleanup(self):
        self.tx.cleanup()

    def recover(self):
        if _busy:
            return
        if fs.exists(JOURNAL) or fs.exists(STAGE) and fs.os.listdir(STAGE):
            self.tx.recover()

    def _check_target(self, path, package, installed):
        owner = None
        for name, record in installed.items():
            for item in record['files']:
                if item['path'] == path:
                    owner = name
                    if fs.exists('/' + path) and file_hash('/' + path) != item['sha256']:
                        raise ValueError('Locally modified file: ' + path)
        if owner is not None and owner != package:
            raise ValueError('File belongs to ' + owner)
        if owner is None and fs.exists('/' + path):
            raise ValueError('Refusing to overwrite unmanaged file: ' + path)
        if path.endswith('.py') and fs.exists('/' + path[:-3] + '.mpy'):
            raise ValueError('Compiled module shadows package: ' + path)

    def _commit(self, entries, before, after):
        self.tx.commit(entries, before, after)

    def _check_running(self, names):
        import sys
        module = sys.modules.get('ok45_desktop')
        desktop = getattr(module, 'CURRENT', None) if module else None
        if desktop:
            paths = {'script:/' + item['path'] for name, record in self.installed()['packages'].items()
                     if name in names for item in record['files'] if item['path'].endswith('.py')}
            if any(window.kind in names or window.kind in paths for window in desktop.wm.windows):
                raise ValueError('Close package application windows before changing their files')

    def install_job(self, names):
        yield from self._install_job(names)

    def bundle_job(self, path):
        bundle = Bundle(path)
        try:
            header = bundle.header
            if isinstance(header.get('api', 1), bool) or header.get('api', 1) != 1:
                raise ValueError('Unsupported software bundle API')
            if header['kind'] != 'software' or 'files' in header:
                raise ValueError('install accepts software package bundles, not system updates')
            index = validate_index({'format': 1, 'packages': header.get('packages')})
            if not index['packages']:
                raise ValueError('Software bundle is empty')
            if sum(item['size'] for package in index['packages'] for item in package['files']) > MAX_TOTAL:
                raise ValueError('Software bundle exceeds transaction budget')
            yield from self._install_job([package['name'] for package in index['packages']], index, bundle)
        finally:
            bundle.close()

    def _install_job(self, names, index=None, bundle=None):
        global _busy
        if _busy:
            raise RuntimeError('Another package operation is active')
        self.recover()
        fs.acquire('apt')
        _busy = True
        try:
            index, plan = self.plan(names, index)
            if not plan:
                if bundle:
                    for package in index['packages']:
                        for item in package['files']:
                            yield from bundle.stage_job(item)
                    bundle.finish()
                yield 'Already up to date'
                return
            self._check_running([package['name'] for package in plan])
            before = self.installed()
            after = {'packages': dict(before['packages'])}
            if len(set(after['packages']).union(package['name'] for package in plan)) > MAX_PACKAGES:
                raise ValueError('Installed package limit is %d' % MAX_PACKAGES)
            entries = []
            stage_sizes = [item['size'] for package in plan for item in package['files']]
            self.tx.prepare(sum(stage_sizes), stage_sizes)
            staged = {}
            for package in plan:
                name = package['name']
                yield 'Stage %s %s' % (name, package['version'])
                old = before['packages'].get(name, {'files': []})
                new_paths = [item['path'] for item in package['files']]
                for item in old['files']:
                    if item['path'] not in new_paths:
                        self._check_target(item['path'], name, before['packages'])
                        entries.append({'id': len(entries), 'path': item['path'],
                                        'had': fs.exists('/' + item['path']), 'install': False})
                for item in package['files']:
                    self._check_target(item['path'], name, before['packages'])
                    entry = {'id': len(entries), 'path': item['path'],
                             'had': fs.exists('/' + item['path']), 'install': True}
                    entries.append(entry)
                    staged[item['path']] = entry
                    if bundle:
                        continue
                    reader, response = self._reader(_join(index['source'], item['source']))
                    hasher, size = hashlib.sha256(), 0
                    try:
                        with open(STAGE + '/new-%d' % entry['id'], 'wb') as file:
                            while True:
                                chunk = reader.read(512)
                                if not chunk:
                                    break
                                size += len(chunk)
                                if size > item['size']:
                                    raise ValueError('Download exceeds declared size')
                                hasher.update(chunk)
                                file.write(chunk)
                                yield None
                    finally:
                        response.close() if response else reader.close()
                    if size != item['size'] or _digest(hasher) != item['sha256']:
                        raise ValueError('Integrity check failed: ' + item['path'])
                after['packages'][name] = {'version': package['version'],
                                          'summary': package.get('summary', ''),
                                          'depends': package.get('depends', []),
                                          'files': package['files']}
                if 'desktop' in package:
                    after['packages'][name]['desktop'] = package['desktop']
            if bundle:
                for package in index['packages']:
                    for item in package['files']:
                        entry = staged.get(item['path'])
                        destination = STAGE + '/new-%d' % entry['id'] if entry else None
                        yield from bundle.stage_job(item, destination)
                bundle.finish()
            if len(json.dumps(after).encode()) > MAX_INDEX:
                raise ValueError('Installed package database exceeds limit')
            yield 'Committing %d packages' % len(plan)
            self._commit(entries, before, after)
            for package in plan:
                yield 'Installed %s %s' % (package['name'], package['version'])
        finally:
            _busy = False
            try:
                self.recover()
            finally:
                fs.release('apt')

    def remove_job(self, names):
        global _busy
        if _busy:
            raise RuntimeError('Another package operation is active')
        self.recover()
        fs.acquire('apt')
        _busy = True
        try:
            before = self.installed()
            names = set(names)
            if not names or any(name not in before['packages'] for name in names):
                raise ValueError('Package is not installed')
            self._check_running(names)
            for name, record in before['packages'].items():
                if name not in names and names.intersection(record.get('depends', [])):
                    raise ValueError('Required by ' + name)
            after = {'packages': dict(before['packages'])}
            entries = []
            fs.mkdirs(STAGE)
            for name in sorted(names):
                for item in before['packages'][name]['files']:
                    self._check_target(item['path'], name, before['packages'])
                    entries.append({'id': len(entries), 'path': item['path'],
                                    'had': fs.exists('/' + item['path']), 'install': False})
                del after['packages'][name]
            yield 'Removing ' + ', '.join(sorted(names))
            self._commit(entries, before, after)
            yield 'Removed ' + ', '.join(sorted(names))
        finally:
            _busy = False
            try:
                self.recover()
            finally:
                fs.release('apt')

    def command_job(self, args):
        sub = args[0] if args else 'help'
        if sub == 'update':
            yield from self.update_job()
        elif sub == 'install' and len(args) > 1:
            if len(args) == 2 and args[1].endswith('.sin'):
                yield from self.bundle_job(args[1])
            else:
                yield from self.install_job(args[1:])
        elif sub == 'remove' and len(args) > 1:
            yield from self.remove_job(args[1:])
        elif sub == 'upgrade':
            yield from self.install_job(list(self.installed()['packages']))
        elif sub == 'source':
            if len(args) > 1:
                self.set_source(args[1])
            yield 'Source: ' + self.source()
            yield 'Only trusted sources; SHA256 is not a signature'
        elif sub == 'list':
            packages = self.installed()['packages']
            for name in sorted(packages):
                yield '%s %s' % (name, packages[name]['version'])
            if not packages:
                yield 'No packages installed'
        elif sub in ('search', 'show'):
            query = ' '.join(args[1:]).lower()
            for package in self.index()['packages']:
                if query in (package['name'] + ' ' + package.get('summary', '')).lower():
                    yield '%s %s - %s' % (package['name'], package['version'], package.get('summary', ''))
                    if sub == 'show':
                        yield 'Depends: ' + ', '.join(package.get('depends', []))
        else:
            yield 'apt update | search | show | list'
            yield 'apt install NAME or /app.sin | remove NAME | upgrade'
            yield 'apt source [local-path or trusted URL]'
