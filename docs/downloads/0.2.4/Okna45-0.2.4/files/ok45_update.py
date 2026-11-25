"""Separate trusted system/software updates; apply with the desktop unloaded."""
import sys
import ok45_fs as fs
from ok45_sin import Bundle, validate_file, file_hash, version_key, MAX_TOTAL
from ok45_tx import Transaction

VERSION = '0.2.4'
ROOT = '/system/update'
SYSTEM_FILES = ('main.py', 'desktop.py', 'apt.py', 'install.py', 'update.py', 'ps.py', 'kill.py',
                'timezone.py', 'ok45_fs.py', 'ok45_tx.py', 'ok45_sin.py', 'ok45_update.py',
                'ok45_kernel.py', 'ok45_ui.py', 'ok45_api.py', 'ok45_registry.py', 'ok45_pkg.py',
                'ok45_desktop.py', 'ok45_time.py', 'ok45_net.py', 'ok45_script.py', 'ok45_store.py', 'updates.py', 'ok45_loader.py')
SOFTWARE_FILES = ('ok45_apps.py', 'ok45_wifi_app.py', 'run.py',
                  'info.py', 'dir.py', 'clear.py', 'df.py', 'pwd.py', 'reboot.py',
                   'copy.py', 'del.py', 'md.py', 'ren.py', 'led.py', 'type.py', 'curl.py',
                    'ok45_run_app.py', 'ok45_store_app.py', 'publish.py')
LEGACY_FILES = ('ok45_legacy.py', 'edit.py', 'clock.py', 'wifi.py', 'sysmon.py', 'web.py',
                'help.py', 'demo_3d.py', 'demo_gfx.py', 'demo_text.py', 'weather.py')


def running_desktop():
    module = sys.modules.get('ok45_desktop')
    return module is not None and getattr(module, 'CURRENT', None) is not None


class Updater:
    def state(self, channel='system'):
        if channel not in ('system', 'software'):
            raise ValueError('Unknown update channel')
        value = fs.load_json(ROOT + '/' + channel + '.json', 16384,
                             {'version': '0.1.0', 'files': {}, 'channel': channel})
        if not isinstance(value, dict) or not isinstance(value.get('files'), dict):
            raise ValueError('Invalid update state')
        version_key(value.get('version'))
        return value

    def command_job(self, args):
        if not args or args[0] == 'status':
            for channel in ('system', 'software'):
                value = self.state(channel)
                if not fs.exists(ROOT + '/' + channel + '.json'):
                    yield '%s: untracked; first full update establishes baseline' % channel
                else:
                    yield '%s: %s%s' % (channel, value['version'], ' (restart required)' if value.get('restart_required') else '')
            yield 'update /path/update.sin | install /path/app.sin'
            yield 'Trusted bundles only; SHA256 is not a signature'
        else:
            yield from self.apply_job(args[0])

    def apply_job(self, path):
        if running_desktop():
            raise RuntimeError('Exit desktop before updating system/bundled software')
        bundle = Bundle(path)
        if bundle.header['kind'] == 'software' and 'packages' in bundle.header:
            bundle.close()
            from ok45_pkg import PackageManager
            yield from PackageManager().bundle_job(path)
            return
        owner = 'update'
        acquired = False
        tx = None
        try:
            fs.acquire(owner)
            acquired = True
            header = bundle.header
            channel = header['kind']
            files = header.get('files')
            if 'packages' in header or not isinstance(files, list) or not 1 <= len(files) <= 48:
                raise ValueError('Update requires 1..48 files, not package metadata')
            version_key(header.get('version'))
            if header.get('api', 1) != 1 or isinstance(header.get('api', 1), bool):
                raise ValueError('Unsupported update API')
            allowed = SYSTEM_FILES if channel == 'system' else SOFTWARE_FILES + LEGACY_FILES
            seen = set()
            for item in files:
                validate_file(item)
                if item['path'] not in allowed or item['path'] in seen:
                    raise ValueError('File outside %s update channel: %s' % (channel, item['path']))
                seen.add(item['path'])
                if fs.exists('/' + item['path'][:-3] + '.mpy'):
                    raise ValueError('Compiled module shadows update: ' + item['path'])
            total = sum(item['size'] for item in files)
            if total > MAX_TOTAL:
                raise ValueError('Update exceeds flash staging budget')
            tx = Transaction(ROOT, ROOT + '/' + channel + '.json')
            tx.recover()
            before = self.state(channel)
            if version_key(header['version']) < version_key(before['version']):
                raise ValueError('Update downgrade refused')
            bases = header.get('from', [])
            if (not isinstance(bases, list) or len(bases) > 16 or
                    any(not isinstance(value, str) for value in bases)):
                raise ValueError('Invalid update base versions')
            if bases and not fs.exists(tx.database):
                raise ValueError('Apply a full update before a delta')
            if bases and before['version'] not in bases:
                raise ValueError('Update does not support current version ' + before['version'])
            after = {'version': header['version'], 'files': dict(before.get('files', {})),
                     'channel': channel, 'restart_required': True}
            entries, by_path = [], {}
            for item in sorted(files, key=lambda item: item['path'] == 'main.py'):
                path = item['path']
                exists = fs.exists('/' + path)
                actual = file_hash('/' + path) if exists else None
                previous = before.get('files', {}).get(path)
                if previous and actual not in (previous, item['sha256']):
                    raise ValueError('Locally modified system/software file: ' + path)
                if actual != item['sha256']:
                    entry = {'id': len(entries), 'path': path, 'had': exists, 'install': True}
                    entries.append(entry)
                    by_path[path] = entry
                after['files'][path] = item['sha256']
            stage_sizes = [item['size'] for item in files if item['path'] in by_path]
            tx.prepare(sum(stage_sizes), stage_sizes)
            yield 'Stage %s update %s (%d changed files)' % (channel, header['version'], len(entries))
            for item in files:
                entry = by_path.get(item['path'])
                destination = tx.stage + '/new-%d' % entry['id'] if entry else None
                yield from bundle.stage_job(item, destination)
            bundle.finish()
            if (not entries and before.get('version') == header['version'] and
                    before.get('files') == after['files']):
                yield 'Already up to date'
                return
            yield 'Commit %s update' % channel
            tx.commit(entries, before, after)
            yield 'Updated %s to %s; restart required' % (channel, header['version'])
        finally:
            bundle.close()
            if acquired:
                try:
                    if tx:
                        tx.recover()
                finally:
                    fs.release(owner)
