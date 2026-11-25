"""Read-only trusted Store. Static GitHub Pages or a local HTTP repository."""
import json
import hashlib
import gc
import ok45_fs as fs
from ok45_sin import Bundle, digest, version_key, safe_relative, MAX_TOTAL, MAX_HEADER

ROOT = '/system/store'
CONFIG = ROOT + '/config.json'
CACHE = ROOT + '/updates.json'
PENDING = ROOT + '/pending.json'
DOWNLOADS = ROOT + '/downloads'
MAX_INDEX = 16384
DEFAULT_SERVER = 'https://niktehnologes.github.io/okna45-store'


def server_url(value):
    if not isinstance(value, str):
        raise ValueError('Use a trusted http(s) server address')
    value = value.rstrip('/')
    if (not 8 <= len(value) <= 256 or not (value.startswith('http://') or value.startswith('https://')) or
            any(ord(ch) <= 32 or ord(ch) > 126 for ch in value) or
            any(ch in value for ch in ('@', '?', '#', '\\')) or
            any(part in ('.', '..') for part in value.split('/')) or not value.split('/')[2]):
        raise ValueError('Use http(s)://host:port, without passwords, spaces or ..')
    return value


def validate_updates(value):
    if (not isinstance(value, dict) or type(value.get('format')) is not int or value['format'] != 1 or
            not isinstance(value.get('channels'), dict) or set(value['channels']) != {'system', 'software'}):
        raise ValueError('Invalid update catalog')
    for channel in ('system', 'software'):
        entries = value['channels'][channel]
        if not isinstance(entries, list) or len(entries) > 16:
            raise ValueError('Update catalog channel limit is 16')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Invalid release entry')
            version_key(entry.get('version'))
            bases = entry.get('from', [])
            if not isinstance(bases, list) or len(bases) > 16:
                raise ValueError('Invalid update bases')
            for base in bases:
                version_key(base)
            size, sha256 = entry.get('size'), entry.get('sha256')
            if type(size) is not int or not 9 <= size <= MAX_TOTAL + MAX_HEADER + 8:
                raise ValueError('Update download outside byte budget')
            if (not isinstance(sha256, str) or len(sha256) != 64 or
                    any(ch not in '0123456789abcdef' for ch in sha256) or not safe_relative(entry.get('source'))):
                raise ValueError('Invalid release source/hash')
            if 'payload_size' in entry or 'file_count' in entry:
                payload, count = entry.get('payload_size'), entry.get('file_count')
                if (type(payload) is not int or not 1 <= payload <= min(MAX_TOTAL, size - 8) or
                        type(count) is not int or not 1 <= count <= min(48, payload)):
                    raise ValueError('Invalid update staging estimate')
            if 'file_sizes' in entry:
                sizes = entry['file_sizes']
                if (not isinstance(sizes, list) or len(sizes) != entry.get('file_count') or
                        any(type(size) is not int or not 1 <= size <= 65536 for size in sizes) or
                        sum(sizes) != entry.get('payload_size')):
                    raise ValueError('Invalid update file sizes')
    return value


def stage_budget(entry, block):
    # Allocation estimate, not a claim about LittleFS metadata/inline layout.
    if 'file_sizes' in entry:
        return sum((size + block - 1) // block * block for size in entry['file_sizes'])
    payload, count = entry.get('payload_size', entry['size']), entry.get('file_count', 48)
    return (payload + count * (block - 1)) // block * block


class StoreService:
    def config(self):
        value = fs.load_json(CONFIG, 1024, {'server': DEFAULT_SERVER})
        if not isinstance(value, dict):
            raise ValueError('Invalid Store settings')
        server = value.get('server') or DEFAULT_SERVER
        server_url(server)
        # Older versions stored a publication token. Never use or expose it;
        # saving these read-only settings removes that obsolete field.
        return {'server': server}

    def configure(self, server):
        from ok45_pkg import PackageManager
        server = server_url(server)
        old = self.config()
        manager = PackageManager()
        manager.set_source(server + '/index.json')
        fs.atomic_json(CONFIG, {'server': server})
        if old['server'] != server:
            fs.remove(CACHE)
            # Previously downloaded trusted updates remain explicit/pending.

    def server(self):
        value = self.config()['server']
        if not value:
            raise ValueError('Set server address in Store Setup first')
        return value

    @staticmethod
    def reader(url):
        gc.collect()
        import urequests
        gc.collect()
        response = urequests.get(url, timeout=10, stream=True)
        if response.status_code != 200:
            status = response.status_code
            response.close()
            raise OSError('Store HTTP %d' % status)
        if getattr(response, 'raw', None) is None:
            response.close()
            raise RuntimeError('urequests streaming response required')
        return response

    def check_job(self, channel='all'):
        if channel not in ('all', 'apps', 'os'):
            raise ValueError('Check apps, os or all')
        server = self.server()
        if channel in ('all', 'os'):
            fs.acquire('store')
            response, temporary = None, CACHE + '.part'
            try:
                yield 'Checking OS catalog'
                response = self.reader(server + '/updates.json')
                try:
                    yield from fs.receive_job(response.raw, temporary, MAX_INDEX)
                finally:
                    response.close()
                    response = None
                gc.collect()
                value = validate_updates(fs.load_json(temporary, MAX_INDEX))
                fs.remove(temporary)
                value['source'] = server
                fs.atomic_json(CACHE, value, MAX_INDEX)
            finally:
                if response:
                    response.close()
                try:
                    fs.remove(temporary)
                finally:
                    fs.release('store')
            del value
            gc.collect()
        if channel in ('all', 'apps'):
            from ok45_pkg import PackageManager
            manager = PackageManager()
            if manager.source() != server + '/index.json':
                manager.set_source(server + '/index.json')
            yield from manager.update_job()
        yield 'Catalogs checked'

    def packages(self):
        from ok45_pkg import PackageManager
        return PackageManager().index()['packages']

    def releases(self):
        value = fs.load_json(CACHE, MAX_INDEX)
        if value is None or value.get('source') != self.server():
            raise ValueError('Check Store catalogs first')
        return validate_updates(value)['channels']

    def candidate(self, channel):
        from ok45_update import Updater, VERSION, ROOT as UPDATE_ROOT
        if channel not in ('system', 'software'):
            raise ValueError('Unknown update channel')
        tracked = fs.exists(UPDATE_ROOT + '/' + channel + '.json')
        current = Updater().state(channel)['version'] if tracked else VERSION
        choices = [item for item in self.releases()[channel]
                   if version_key(item['version']) >= version_key(current) and
                   (not item.get('from') or tracked and current in item['from'])]
        choices.sort(key=lambda item: (version_key(item['version']), bool(item.get('from'))), reverse=True)
        return choices[0] if choices else None

    def pending(self):
        value = fs.load_json(PENDING, 4096, {'updates': []})
        if not isinstance(value, dict) or not isinstance(value.get('updates'), list) or len(value['updates']) > 2:
            raise ValueError('Invalid downloaded update list')
        seen = set()
        for entry in value['updates']:
            if not isinstance(entry, dict):
                raise ValueError('Invalid downloaded update')
            channel = entry.get('channel')
            if (channel not in ('system', 'software') or channel in seen or
                    entry.get('path') != DOWNLOADS + '/' + channel + '.sin'):
                raise ValueError('Unsafe downloaded update path')
            validate_updates({'format': 1, 'channels': {
                'system': [entry] if channel == 'system' else [],
                'software': [entry] if channel == 'software' else []}})
            seen.add(channel)
        return value['updates']

    def download_job(self, channel='all'):
        channels = ('system', 'software') if channel == 'all' else (channel,)
        for name in channels:
            release = self.candidate(name)
            if release is None:
                yield 'No compatible ' + name + ' release'
                continue
            fs.acquire('store')
            response = None
            path = DOWNLOADS + '/' + name + '.sin'
            temporary = path + '.part'
            try:
                fs.mkdirs(DOWNLOADS)
                pending_before = self.pending()
                statvfs = getattr(fs.os, 'statvfs', None)
                if statvfs:
                    stats = statvfs('/')
                    block = stats[1] or stats[0]
                    download = (release['size'] + block - 1) // block * block
                    stage = max([stage_budget(release, block)] +
                                [stage_budget(item, block) for item in pending_before])
                    if block * stats[4] < download + stage + 32768:
                        raise OSError('Not enough flash for download AND staging; apply one channel at a time')
                yield 'Download %s %s' % (name, release['version'])
                response = self.reader(self.server() + '/' + release['source'])
                hasher, size, announced = hashlib.sha256(), 0, -1
                with open(temporary, 'wb') as output:
                    while True:
                        chunk = response.raw.read(512)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > release['size']:
                            raise ValueError('Download exceeds declared size')
                        hasher.update(chunk)
                        output.write(chunk)
                        percent = size * 100 // release['size']
                        if percent // 10 != announced:
                            announced = percent // 10
                            yield '%s %d%%' % (name, percent)
                        else:
                            yield None
                    output.flush()
                if size != release['size'] or digest(hasher) != release['sha256']:
                    raise ValueError('Update download integrity check failed')
                bundle = Bundle(temporary)
                try:
                    if (bundle.header['kind'] != name or 'packages' in bundle.header or
                             bundle.header.get('version') != release['version'] or
                             bundle.header.get('from', []) != release.get('from', [])):
                        raise ValueError('Downloaded update does not match catalog')
                    if 'file_sizes' in release and release['file_sizes'] != [item['size'] for item in bundle.header['files']]:
                        raise ValueError('Downloaded update staging sizes do not match catalog')
                finally:
                    bundle.close()
                fs.replace(temporary, path)
                pending = [item for item in pending_before if item['channel'] != name]
                pending.append(dict(release, channel=name, path=path))
                fs.atomic_json(PENDING, {'updates': pending})
                fs.sync()
                yield 'Ready to apply ' + name
            finally:
                if response:
                    response.close()
                fs.remove(temporary)
                fs.release('store')

    def apply_pending_job(self):
        from ok45_update import Updater, running_desktop
        if running_desktop():
            raise RuntimeError('Leave desktop before applying OS updates')
        updates = sorted(self.pending(), key=lambda entry: entry['channel'] != 'system')
        if not updates:
            yield 'No downloaded updates'
            return
        for entry in updates:
            hasher, size = hashlib.sha256(), 0
            yield 'Verify downloaded ' + entry['channel']
            with open(entry['path'], 'rb') as file:
                while True:
                    chunk = file.read(512)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > entry['size']:
                        raise ValueError('Downloaded update was modified')
                    hasher.update(chunk)
                    yield None
            if size != entry['size'] or digest(hasher) != entry['sha256']:
                raise ValueError('Downloaded update was modified; download again')
        # Verify every download before the first channel commit. Channel
        # transactions remain independent; a later install error is recoverable.
        for entry in updates:
            yield from Updater().apply_job(entry['path'])
            fs.atomic_json(PENDING, {'updates': [item for item in self.pending()
                                               if item['channel'] != entry['channel']]})
            fs.remove(entry['path'])
        yield 'Updates applied; reboot required'

    def command_job(self, args):
        action = args[0] if args else 'status'
        if action == 'check':
            yield from self.check_job()
        elif action == 'download':
            yield from self.download_job(args[1] if len(args) > 1 else 'all')
        elif action == 'apply':
            yield from self.apply_pending_job()
        elif action == 'server' and len(args) == 2:
            self.configure(args[1])
            yield 'Store server saved; Check to refresh catalogs'
        elif action == 'status':
            yield 'Server: ' + (self.config()['server'] or 'not configured')
            for entry in self.pending():
                yield 'Downloaded %s %s' % (entry['channel'], entry['version'])
            yield 'updates check | download [all|system|software] | apply'
            yield 'updates server trusted-URL; GitHub Pages needs no key'
        else:
            raise ValueError('updates check | download [all|system|software] | apply | server URL')
