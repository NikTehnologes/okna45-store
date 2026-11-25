"""Read-only graphical app catalog and separate OS downloads."""
from ok45_api import Application, UP, DOWN
from ok45_ui import WHITE, BLACK, LIGHT, SILVER, NAVY
from ok45_store import StoreService
import gc
import sys

TABS = ('Apps', 'OS', 'Setup')


class Store(Application):
    title = 'Store'
    def __init__(self, desktop, window, path=None):
        super().__init__(desktop, window)
        self.service = StoreService()
        config = self.service.config()
        self.server = config['server']
        self.tab = 'Apps'
        self.selected, self.scroll = 0, 0
        self.packages, self.installed, self.os_rows = [], {}, []
        self.logs = []
        self.status = 'Check to refresh catalogs'
        self.busy, self.job, self.confirm = False, None, False
        self.reload()

    def reload(self):
        import ok45_fs as fs
        self.packages, self.installed, self.os_rows = [], {}, []
        gc.collect()
        if self.tab == 'Apps':
            try:
                index = fs.load_json('/system/pkg/index.json', 16384, {'packages': []})
                packages = index['packages']
                if not isinstance(packages, list) or len(packages) > 32:
                    raise ValueError('Invalid cached catalog')
                for p in packages:
                    if (not isinstance(p, dict) or not isinstance(p.get('name'), str) or not 1 <= len(p['name']) <= 32 or
                            not isinstance(p.get('version'), str) or len(p['version']) > 17 or
                            not isinstance(p.get('summary', ''), str) or len(p.get('summary', '')) > 160):
                        raise ValueError('Invalid cached preview')
                    self.packages.append({'name': p['name'], 'version': p['version'], 'summary': p.get('summary', '')})
                del index, packages
                records = fs.load_json('/system/pkg/installed.json', 16384, {'packages': {}})['packages']
                if not isinstance(records, dict) or len(records) > 32:
                    raise ValueError('Invalid installed preview')
                for name, record in records.items():
                    if not isinstance(record, dict) or not isinstance(record.get('version'), str):
                        raise ValueError('Invalid installed preview')
                    self.installed[name] = record['version']
                del records
            except (ValueError, OSError, KeyError, TypeError) as error:
                self.packages, self.installed = [], {}
                self.status = 'Cache: ' + str(error)[:100]
            self.selected = min(self.selected, max(0, len(self.packages) - 1))
            self.scroll = min(self.scroll, self.selected)
        elif self.tab == 'OS':
            from ok45_update import Updater, VERSION, ROOT as UPDATE_ROOT
            pending = self.service.pending()
            for channel in ('system', 'software'):
                tracked = fs.exists(UPDATE_ROOT + '/' + channel + '.json')
                current = Updater().state(channel)['version'] if tracked else VERSION
                try:
                    release = self.service.candidate(channel)
                except (ValueError, OSError):
                    release = None
                self.os_rows.append({'channel': channel, 'current': current, 'tracked': tracked,
                                     'available': release['version'] if release else None,
                                     'downloaded': next((item['version'] for item in pending
                                                          if item['channel'] == channel), None)})
        gc.collect()
        self.invalidate()

    def write(self, message):
        self.status = str(message)[:160]
        self.logs = (self.logs + [self.status])[-4:]
        self.invalidate()

    def start(self, messages, name):
        if self.busy:
            messages.close()
            return
        def task():
            try:
                for message in messages:
                    if message:
                        self.write(message)
                    yield 0
            except Exception as error:
                printer = getattr(sys, 'print_exception', None)
                if printer:
                    printer(error)
                self.write('Error: ' + str(error))
            finally:
                messages.close()
                self.busy, self.job = False, None
                self.reload()
                self.desktop.refresh_apps()
        self.packages, self.installed, self.os_rows = [], {}, []
        gc.collect()
        self.busy = True
        try:
            self.job = self.desktop.scheduler.spawn('store-' + name, task(), owner=self.window.id)
        except Exception:
            self.busy = False
            messages.close()
            raise
        self.invalidate()

    def cancel(self):
        if self.job is not None:
            self.desktop.scheduler.cancel(self.job)
            self.busy, self.job = False, None
            self.write('Operation cancelled')

    def close(self):
        self.cancel()
        return True

    def tick(self):
        if self.busy and self.job is not None and self.desktop.scheduler.find(self.job) is None:
            self.busy, self.job = False, None
            self.write('Operation stopped')

    def visible_rows(self):
        return max(1, (self.window.client()[3] - 88) // 12)

    def select(self, delta):
        self.selected = max(0, min(max(0, len(self.packages) - 1), self.selected + delta))
        self.scroll = min(self.scroll, self.selected)
        if self.selected >= self.scroll + self.visible_rows():
            self.scroll = self.selected - self.visible_rows() + 1
        self.invalidate()

    def key(self, code):
        if self.confirm:
            if code in (ord('y'), ord('Y')):
                self.activate({'action': 'confirm_apply'})
            elif code in (27, ord('n'), ord('N')):
                self.activate({'action': 'dismiss'})
            return
        if self.tab == 'Apps' and code in (UP, DOWN):
            self.select(-1 if code == UP else 1)
            return
        if self.busy or self.tab != 'Setup':
            return
        value = self.server
        if code in (8, 127):
            value = value[:-1]
        elif code in (10, 13):
            self.desktop.set_mode('pointer')
            self.status = 'Click Save'
        elif 32 <= code <= 126 and len(value) < 256:
            value += chr(code)
        self.server = value
        self.invalidate()

    def dialog_rect(self):
        x, y, w, h = self.window.client()
        return (x + 6, y + (h - 84) // 2, w - 12, 84)

    def controls(self):
        if self.confirm:
            x, y, w, h = self.dialog_rect()
            return [{'action': action, 'label': label, 'rect': [x + 8 + index * ((w - 19) // 2 + 3),
                     y + h - 24, (w - 19) // 2, 18]}
                    for index, (action, label) in enumerate((('confirm_apply', 'Apply'), ('dismiss', 'Cancel')))]
        x, y, w, h = self.window.client()
        width = (w - 2 - 2 * len(TABS)) // len(TABS)
        controls = [{'action': 'tab', 'tab': tab, 'label': tab,
                      'selected': tab == self.tab, 'enabled': not self.busy,
                     'rect': [x + 2 + index * (width + 2), y + 2, width, 18]}
                    for index, tab in enumerate(TABS)]
        if self.tab == 'Apps':
            actions = (('check', 'Check'), ('get', 'Get'), ('upgrade', 'All'), ('remove', 'Del'))
            controls.extend({'action': 'select', 'index': self.scroll + row, 'button': False,
                             'label': package['name'], 'rect': [x + 2, y + 26 + row * 12, w - 26, 12]}
                            for row, package in enumerate(self.packages[self.scroll:self.scroll + self.visible_rows()]))
            controls.extend({'action': action, 'label': label, 'rect': [x + w - 22, y + 26 + index * 22, 18, 18]}
                            for index, (action, label) in enumerate((('prev', '^'), ('next', 'v'))))
        elif self.tab == 'OS':
            actions = (('check', 'Check'), ('download_system', 'Sys'), ('download_software', 'Soft'),
                       ('apply', 'Apply'), ('cancel_job', 'Stop'))
        else:
            actions = (('save_settings', 'Save'), ('check', 'Check'), ('input', 'Input'), ('wifi', 'WiFi'))
            controls.append({'action': 'field', 'label': 'Server', 'button': False,
                             'rect': [x + 4, y + 33, w - 8, 18]})
        buttons = self.toolbar(actions)
        for control in buttons:
            action = control['action']
            control['enabled'] = not self.busy or action == 'cancel_job'
            if action in ('get', 'remove'):
                control['enabled'] = not self.busy and bool(self.packages)
            if action == 'apply':
                control['enabled'] = not self.busy and any(row['downloaded'] for row in self.os_rows)
        controls.extend(buttons)
        return controls

    def activate(self, control):
        action = control['action']
        try:
            if action == 'tab':
                if self.busy:
                    return
                self.tab = control['tab']
                self.reload()
                self.desktop.set_mode('pointer')
            elif action == 'field':
                if not self.busy:
                    self.desktop.set_mode('input')
            elif action == 'cancel_job':
                self.cancel()
            elif action == 'select':
                self.selected = control['index']
            elif action in ('prev', 'next'):
                self.select(-1 if action == 'prev' else 1)
            elif self.busy:
                return
            elif action == 'input':
                self.desktop.set_mode('input')
            elif action == 'save_settings':
                self.service.configure(self.server)
                self.server = self.service.server()
                self.write('Read-only settings saved; no key needed')
                self.reload()
                self.desktop.set_mode('pointer')
            elif action == 'wifi':
                self.desktop.open('wifi')
            elif action == 'check':
                channel = 'apps' if self.tab == 'Apps' else 'os' if self.tab == 'OS' else 'all'
                self.start(self.service.check_job(channel), 'check')
            elif action in ('get', 'remove', 'upgrade'):
                from ok45_pkg import PackageManager
                manager = PackageManager()
                if action == 'upgrade':
                    # One transaction per app keeps All inside the 64 KiB
                    # device staging budget; dependencies retain apt planning.
                    def upgrade_all():
                        for name in sorted(manager.installed()['packages']):
                            yield from manager.install_job([name])
                        yield 'Installed applications checked/upgraded'
                    messages = upgrade_all()
                else:
                    name = self.packages[self.selected]['name']
                    messages = manager.install_job([name]) if action == 'get' else manager.remove_job([name])
                self.start(messages, action)
            elif action in ('download_system', 'download_software'):
                self.start(self.service.download_job(action[9:]), 'download')
            elif action == 'apply':
                self.confirm = True
                self.desktop.set_mode('pointer')
                self.write('Leave desktop, apply and reboot? Y/N')
            elif action == 'confirm_apply':
                self.confirm = False
                self.desktop.launch('updates apply')
            elif action == 'dismiss':
                self.confirm = False
                self.desktop.exiting = False
                self.desktop.shell_launch = None
                self.write('Apply cancelled; downloads kept')
        except Exception as error:
            printer = getattr(sys, 'print_exception', None)
            if printer:
                printer(error)
            self.write('Error: ' + str(error))
        self.invalidate()

    def semantic(self):
        return {'tab': self.tab, 'server': self.server, 'read_only': True,
                'busy': self.busy, 'status': self.status, 'confirm_apply': self.confirm,
                'dialog': 'Apply downloaded OS updates?' if self.confirm else None,
                'packages': [{'name': p['name'], 'version': p['version'], 'summary': p.get('summary', ''),
                              'installed': self.installed.get(p['name'])}
                             for p in self.packages], 'selected': self.selected, 'scroll': self.scroll,
                'updates': self.os_rows, 'lines': [self.status] + self.logs[-3:]}

    def draw(self, canvas, rect):
        x, y, w, h = rect
        columns = max(1, (w - 8) // 8)
        canvas.fill(rect, LIGHT)
        if self.tab == 'Apps':
            for row, package in enumerate(self.packages[self.scroll:self.scroll + self.visible_rows()]):
                index = self.scroll + row
                selected = index == self.selected
                ry = y + 26 + row * 12
                canvas.fill((x + 2, ry, w - 26, 12), NAVY if selected else WHITE)
                flag = '+' if package['name'] in self.installed else ' '
                label = flag + package['name'] + ' ' + package['version']
                canvas.text(x + 4, ry + 2, label[:max(1, (w - 32) // 8)], WHITE if selected else BLACK)
            if not self.packages:
                canvas.text(x + 4, y + 30, 'Working / close to stop' if self.busy else 'No catalog. Apps -> Check')
            else:
                package = self.packages[self.selected]
                current = self.installed.get(package['name'], 'not installed')
                canvas.text(x + 4, y + h - 64, ('Local: ' + current)[:columns])
                canvas.text(x + 4, y + h - 52, package.get('summary', '')[:columns])
        elif self.tab == 'OS':
            for index, row in enumerate(self.os_rows):
                ry = y + 28 + index * 30
                canvas.text(x + 4, ry, ('%s %s%s' % (row['channel'], row['current'],
                            '' if row['tracked'] else ' untracked'))[:columns])
                canvas.text(x + 4, ry + 12, ('Server: ' + (row['available'] or 'Check / none'))[:columns])
            pending = ','.join(row['channel'] for row in self.os_rows if row['downloaded'])
            canvas.text(x + 4, y + h - 64, ('Downloaded: ' + (pending or 'none'))[:columns])
            canvas.text(x + 4, y + h - 52, 'Sys / Soft -> Apply -> reboot'[:columns])
        else:
            canvas.text(x + 4, y + 22, 'Trusted catalog / Pages URL'[:columns])
            canvas.fill((x + 4, y + 33, w - 8, 18), WHITE)
            canvas.bevel((x + 4, y + 33, w - 8, 18), False)
            marker = '_' if self.desktop.wm.input_mode == 'input' else ''
            canvas.text(x + 7, y + 38, (self.server + marker)[-columns:])
            canvas.text(x + 4, y + 67, 'Downloads only. No tokens.'[:columns])
            canvas.text(x + 4, y + 83, 'Publish manually from computer.'[:columns])
            canvas.text(x + 4, y + 99, 'HTTP is plain; trust the source.'[:columns])
        canvas.fill((x, y + h - 42, w, 42), SILVER)
        canvas.text(x + 4, y + h - 40, self.status[:columns])
        canvas.text(x + 4, y + h - 30, self.status[columns:columns * 2])
        if self.confirm:
            dx, dy, dw, dh = self.dialog_rect()
            canvas.fill((dx, dy, dw, dh), SILVER)
            canvas.bevel((dx, dy, dw, dh))
            canvas.text(dx + 8, dy + 8, 'Apply downloaded OS updates?')
            canvas.text(dx + 8, dy + 25, 'Desktop closes; Pico reboots.')
            canvas.text(dx + 8, dy + 42, 'Unsaved notes ask separately.')
        self.draw_controls(canvas)
