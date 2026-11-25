"""Okna45 0.2 desktop. One display owner, registered apps and tabbed launcher."""
import gc
import time
import sys
import ok45_kernel as kernel
import ok45_time as clock
from ok45_registry import Registry, CATEGORIES
from ok45_ui import WindowManager, TOP, BOTTOM, WIDTH, SILVER, NAVY, WHITE, BLACK, contains, intersection
from ok45_api import LEFT, UP, DOWN, RIGHT
from ok45_loader import Loader

CURRENT = None
VERSION = '0.2.4'


def snapshot():
    return CURRENT.snapshot() if CURRENT else {'active': False, 'version': VERSION}


class Desktop:
    def __init__(self, term):
        self.term = term
        self.scheduler = kernel.Scheduler()
        self.registry = Registry()
        self.loader = Loader()
        # Reserve enough heap for text, imports and filesystem transactions.
        self.wm = WindowManager(term.d, limit=4 if gc.mem_free() >= 80000 else 2)
        self.wm.draw_overlay = self.draw_menu
        self.wm.draw_background = self.draw_icons
        self.menu = False
        self.menu_index = 0
        self.menu_tab = 'Tools'
        self.menu_page = 0
        self.shell_launch = None
        self.moving = False
        self.exit_requested = False
        self.exiting = False
        self.model_version = 0
        self.status = 'Ready'
        self.keys_processed = 0

    def changed(self):
        self.model_version += 1

    def set_mode(self, mode):
        if self.wm.input_mode != mode:
            self.wm.set_input_mode(mode)
            window = self.wm.get()
            if window and window.app:
                getattr(window.app, 'mode_changed', window.app.invalidate)()
        self.moving = mode == 'move'

    def open(self, kind, path=None):
        record = self.registry.get(kind)
        if record is None:
            self.status = 'Unknown app: ' + kind
            return None
        if record['type'] == 'terminal':
            mode = record.get('mode', 'auto')
            return self.launch('/' + record['entry'], mode)
        if path is None and record.get('singleton', True):
            for window in self.wm.windows:
                if window.kind == kind:
                    self.wm.focus(window.id)
                    self.set_mode('pointer')
                    self.changed()
                    return window
        gc.collect()
        self.loader.prune(self.wm.windows)
        if gc.mem_free() < 32000:
            self.status = 'Low heap; close a window'
            return None
        offset = (len(self.wm.windows) % 3) * 12
        w, h = record.get('size', (304, 194) if kind == 'store' else
                          (264, 172) if kind in ('notes', 'console', 'packages', 'files', 'tasks', 'wifi', 'run_app') else (232, 150))
        window = None
        try:
            x, y = min(12 + offset, WIDTH - w), min(TOP + 6 + offset, BOTTOM - h)
            window = self.wm.add(kind, record['title'], (x, y, w, h))
            if record['type'] == 'window':
                window.app = self.registry.create(record, self, window)
            else:
                window.app = self.loader.create(kind, self, window, path=path)
            self.scheduler.spawn(kind + '-%d' % window.id, self.app_task(window), owner=window.id)
        except Exception as error:
            if window is not None:
                self.scheduler.cancel_owner(window.id)
                self.wm.close(window.id)
                window.app = None
            self.loader.prune(self.wm.windows)
            printer = getattr(sys, 'print_exception', None)
            if printer:
                printer(error)
            self.status = str(error)
            self.changed()
            return None
        self.status = 'Opened ' + window.title
        self.set_mode('pointer')
        self.changed()
        return window

    def launch(self, value, mode='auto'):
        if mode not in ('auto', 'window', 'terminal', 'gfx'):
            raise ValueError('Mode must be auto, window, terminal or gfx')
        parts = value.strip().split()
        if not parts:
            raise ValueError('Enter an application, command or /script.py')
        target, args = parts[0], parts[1:]
        record = self.registry.get(target.lower())
        if record is None and target.lower() == 'run' and not args:
            record = self.registry.get('run_app')
        if record and not args and mode == 'auto':
            return self.open(record['id'])
        if record and record['type'] in ('builtin', 'window') and not args:
            return self.open(record['id'])
        if record and record['type'] == 'terminal':
            target = '/' + record['entry']
            mode = record.get('mode', 'auto') if mode == 'auto' else mode
        if target.startswith('/') or target.endswith('.py'):
            from ok45_script import file_path, kind, window_app
            target = file_path(target)
            gc.collect()
            selected = kind(target) if mode == 'auto' else mode
            if selected == 'window':
                if gc.mem_free() < 32000:
                    raise RuntimeError('Low heap; close a window')
                identity = 'window:' + target
                for window in self.wm.windows:
                    if window.kind == identity:
                        self.wm.focus(window.id)
                        self.set_mode('pointer')
                        return window
                window = self.wm.add(identity, target.rsplit('/', 1)[-1][:28], (8, 24, 264, 172))
                try:
                    window.app = window_app(target, self, window, args)
                    self.scheduler.spawn('script-%d' % window.id, self.app_task(window), owner=window.id)
                except Exception:
                    self.scheduler.cancel_owner(window.id)
                    self.wm.close(window.id)
                    window.app = None
                    self.loader.prune(self.wm.windows)
                    raise
                self.set_mode('pointer')
                self.status = 'Opened ' + window.title
                self.changed()
                return window
            if selected == 'terminal':
                return self.text_script(target, args)
            option = '--gfx ' if selected == 'gfx' else '--terminal '
            value = 'run ' + option + target + (' ' + ' '.join(args) if args else '')
        else:
            parts = value.strip().split()
            if parts[0] not in ('updates', 'update') or len(parts) < 2 or (parts[0] == 'updates' and parts[1] != 'apply'):
                window = self.open('console')
                if window is not None:
                    self.console_command(window.app, value)
                return window
        self.shell_launch = value
        self.exiting = True
        self.status = 'Leave desktop to run ' + value[:80]
        self.changed()
        return None

    def text_script(self, path, args=None):
        for window in self.wm.windows:
            if window.kind == 'script:' + path:
                self.wm.focus(window.id)
                return window
        gc.collect()
        self.loader.prune(self.wm.windows)
        window = None
        try:
            window = self.wm.add('script:' + path, path.rsplit('/', 1)[-1][:28], (8, 24, 264, 172))
            window.app = self.loader.create(window.kind, self, window, path)
            window.app.start_script(args)
            self.status = 'Running in text window'
            self.set_mode('pointer')
            self.changed()
            return window
        except Exception:
            if window is not None:
                self.scheduler.cancel_owner(window.id)
                self.wm.close(window.id)
                window.app = None
            self.loader.prune(self.wm.windows)
            raise

    def close(self, identity, force=False):
        window = self.wm.get(identity)
        if window is None:
            return True
        if not force and not window.app.close():
            self.wm.focus(identity)
            self.set_mode('pointer')
            if self.menu:
                self.toggle_menu(False)
            self.changed()
            return False
        self.scheduler.cancel_owner(identity)
        self.wm.close(identity)
        window.app = None
        self.loader.prune(self.wm.windows)
        gc.collect()
        self.changed()
        return True

    def app_task(self, window):
        interval = max(20, min(60000, getattr(window.app, 'interval_ms', 1000)))
        if window.kind == 'cube':
            interval = 200
        while True:
            window.app.tick()
            self.changed()
            yield interval

    def menu_rect(self):
        return (3, 32, 310, 185)

    def refresh_apps(self):
        self.registry.reload()
        self.wm.damage.add((0, TOP, WIDTH, BOTTOM - TOP))
        self.menu_page = 0
        self.changed()

    def icon_controls(self):
        # Desktop shortcuts for installed software; Start has the complete catalog.
        installed = [item for item in self.registry.items if item['package']][:12]
        return [{'app': item['id'], 'label': item['title'], 'action': 'open',
                 'icon': item['icon'], 'rect': [6 + (index % 4) * 76, 30 + (index // 4) * 52, 72, 48]}
                for index, item in enumerate(installed)]

    def draw_icons(self, canvas):
        for control in self.icon_controls():
            x, y, w, h = control['rect']
            canvas.icon(x + 26, y + 4, control['icon'], WHITE)
            canvas.text(x + 4, y + 29, control['label'][:8], WHITE)

    def menu_tabs(self):
        return [{'action': 'tab', 'tab': name, 'label': name, 'selected': name == self.menu_tab,
                 'rect': [6 + index * 61, 36, 59, 22]} for index, name in enumerate(CATEGORIES)]

    def menu_controls(self):
        count = len(self.registry.category(self.menu_tab))
        return self.menu_tabs() + self.menu_entries() + [
            {'action': 'page_prev', 'label': '<', 'enabled': self.menu_page > 0, 'rect': [6, 192, 26, 20]},
            {'action': 'page_next', 'label': '>', 'enabled': (self.menu_page + 1) * 6 < count, 'rect': [35, 192, 26, 20]},
            {'action': 'console', 'label': 'Console', 'rect': [68, 192, 82, 20]},
            {'action': 'restart', 'label': 'Restart', 'rect': [154, 192, 82, 20]}]

    def toggle_menu(self, visible=None):
        self.menu = not self.menu if visible is None else visible
        if self.menu:
            self.set_mode('pointer')
            self.hover_menu()
        self.wm.damage.add(self.menu_rect())
        self.changed()

    def menu_entries(self):
        entries = self.registry.category(self.menu_tab)[self.menu_page * 6:(self.menu_page + 1) * 6]
        return [{'app': item['id'], 'label': item['title'], 'action': 'open',
                 'category': item['category'], 'icon': item['icon'], 'type': item['type'],
                 'rect': [6 + (index % 3) * 101, 63 + (index // 3) * 61, 98, 56]}
                for index, item in enumerate(entries)]

    def hover_menu(self):
        selected = -1
        for index, entry in enumerate(self.menu_controls()):
            if contains(entry['rect'], self.wm.pointer.x, self.wm.pointer.y):
                selected = index
                break
        if selected != self.menu_index:
            self.menu_index = selected
            self.wm.damage.add(self.menu_rect())

    def draw_menu(self, canvas):
        if not self.menu or not intersection(self.menu_rect(), canvas.region):
            return
        x, y, w, h = self.menu_rect()
        canvas.fill((x, y, w, h), SILVER)
        canvas.bevel((x, y, w, h))
        for index, entry in enumerate(self.menu_controls()):
            rx, ry, rw, rh = entry['rect']
            selected = self.menu_index == index
            selected = selected or entry.get('selected', False)
            if entry['action'] == 'open':
                canvas.fill(entry['rect'], NAVY if selected else SILVER)
                canvas.bevel(entry['rect'], not selected)
                canvas.icon(rx + (rw - 16) // 2, ry + 7, entry['icon'], WHITE if selected else NAVY)
                label = entry['label'][:11]
                canvas.text(rx + max(2, (rw - len(label) * 8) // 2), ry + 33, label, WHITE if selected else BLACK)
            else:
                canvas.button(entry['rect'], entry['label'], selected, entry.get('enabled', True))

    def move_pointer(self, code):
        step = self.wm.pointer.step
        dx = -step if code == LEFT else step if code == RIGHT else 0
        dy = -step if code == UP else step if code == DOWN else 0
        if self.moving:
            actual = self.wm.move(dx, dy)
            self.wm.pointer.move(*actual)
            window = self.wm.get()
            if window and actual != (0, 0):
                window.app.moved(*actual)
        else:
            self.wm.pointer.move(dx, dy)
            if self.menu:
                self.hover_menu()

    def click_pointer(self):
        x, y = self.wm.pointer.x, self.wm.pointer.y
        window = self.wm.get()
        if window and getattr(window.app, 'confirm', False):
            window.app.click(x, y)
            return
        if self.menu:
            for entry in self.menu_controls():
                if contains(entry['rect'], x, y):
                    action = entry['action']
                    if not entry.get('enabled', True):
                        return
                    if action == 'tab':
                        self.menu_tab, self.menu_page = entry['tab'], 0
                        self.hover_menu()
                        self.wm.damage.add(self.menu_rect())
                        return
                    if action in ('page_prev', 'page_next'):
                        self.menu_page += -1 if action == 'page_prev' else 1
                        self.hover_menu()
                        self.wm.damage.add(self.menu_rect())
                        return
                    self.toggle_menu(False)
                    if action == 'open':
                        self.open(entry['app'])
                    elif action == 'console':
                        self.open('console')
                    else:
                        self.shell_launch = 'reboot'
                        self.exiting = True
                    return
            # Dismiss without clicking through a menu onto a hidden window.
            self.toggle_menu(False)
            return
        action, identity = self.wm.hit_test(x, y)
        if action == 'background':
            for control in self.icon_controls():
                if contains(control['rect'], x, y):
                    self.open(control['app'])
                    return
        if action == 'start':
            self.toggle_menu()
            return
        window = self.wm.get(identity) if identity is not None else None
        if window is None:
            return
        self.wm.focus(identity)
        if action == 'minimize':
            self.wm.minimize(identity)
        elif action == 'close':
            self.close(identity)
        elif action == 'move':
            self.set_mode('move')
            self.status = 'Move: arrows; Enter drops'
        elif action == 'client' and not window.app.click(x, y):
            if self.wm.get(identity) is window:
                self.set_mode('input')
                self.status = 'Window input; Tab returns pointer'

    def pointer_target(self):
        x, y = self.wm.pointer.x, self.wm.pointer.y
        window = self.wm.get()
        if window and getattr(window.app, 'confirm', False):
            for control in window.app.controls():
                if contains(control['rect'], x, y):
                    target = dict(control)
                    target['window_id'] = window.id
                    return target
            return {'action': 'dialog', 'window_id': window.id}
        if self.menu:
            for entry in self.menu_controls():
                if contains(entry['rect'], x, y):
                    return dict(entry)
            return {'action': 'dismiss_menu'}
        action, identity = self.wm.hit_test(x, y)
        if action == 'background':
            for control in self.icon_controls():
                if contains(control['rect'], x, y):
                    return dict(control)
        window = self.wm.get(identity) if identity is not None else None
        if action == 'client' and window:
            for control in window.app.controls():
                if contains(control['rect'], x, y):
                    target = dict(control)
                    target['window_id'] = identity
                    return target
        return {'action': action, 'window_id': identity}

    def key(self, code):
        try:
            self.handle_key(code)
        finally:
            # Observers can use this as a completion cursor, not a receipt count.
            self.keys_processed += 1
            self.changed()

    def handle_key(self, code):
        window = self.wm.get()
        if window and getattr(window.app, 'confirm', False):
            if getattr(window.app, 'file_dialog', None) and self.wm.input_mode == 'input':
                if code == 9:
                    self.set_mode('pointer')
                else:
                    window.app.key(code)
                return
            if code in (LEFT, UP, DOWN, RIGHT):
                self.move_pointer(code)
            elif code in (10, 13):
                self.click_pointer()
            elif code == 9 and getattr(window.app, 'file_dialog', None):
                self.set_mode('input')
            elif code != 9:
                window.app.key(code)
            return
        if self.moving:
            if code in (LEFT, UP, DOWN, RIGHT):
                self.move_pointer(code)
            elif code in (9, 10, 13, 27):
                self.set_mode('pointer')
                self.status = 'Window placed'
            return
        if self.menu:
            if code in (LEFT, UP, DOWN, RIGHT):
                self.move_pointer(code)
            elif code in (10, 13):
                self.click_pointer()
            elif code in (27, ord('~')):
                self.toggle_menu(False)
            elif code == 9:
                self.toggle_menu(False)
                if window:
                    self.set_mode('input')
            return
        if code == 9:
            if self.wm.input_mode == 'input':
                self.set_mode('pointer')
            elif window:
                self.set_mode('input')
            else:
                self.status = 'Select a window first'
        elif code == 27:
            if self.wm.input_mode == 'input':
                self.set_mode('pointer')
            else:
                self.toggle_menu(True)
        elif self.wm.input_mode == 'input' and window:
            # CardKB delivers finished characters, not modifier key events.
            window.app.key(code)
        elif code in (LEFT, UP, DOWN, RIGHT):
            self.move_pointer(code)
        elif code in (10, 13):
            self.click_pointer()
        elif code == ord('~'):
            self.toggle_menu()

    def request_exit(self):
        if any(getattr(window.app, 'confirm', False) for window in self.wm.windows):
            return
        for window in self.wm.windows[:]:
            if getattr(window.app, 'dirty', False) and not self.close(window.id):
                self.status = 'Resolve unsaved note before exit'
                return
        for window in self.wm.windows[:]:
            if not self.close(window.id):
                self.status = 'Wait for app/input to finish before restart'
                return
        self.exit_requested = True

    def console_command(self, console, value):
        parts = value.split()
        command, args = parts[0].lower(), parts[1:]
        if command == 'help':
            console.write('open APP | run /script.py\nps | kill ID | apt ... | install FILE.sin\nupdates ... | timezone OFFSET\necho TEXT | exit | reboot\nUp/Down: history; Left/Right: page')
            console.write('Apps: ' + ', '.join(item['id'] for item in self.registry.items))
        elif command == 'open' and args:
            self.open(args[0], path=args[1] if len(args) > 1 else None)
        elif command == 'run' and args:
            mode = 'auto'
            if args[0] in ('--terminal', '--gfx'):
                mode, args = args[0][2:], args[1:]
            self.launch(' '.join(args), mode)
        elif command == 'publish':
            console.write('Store is read-only; publish manually on GitHub from a computer')
        elif command == 'ps':
            for task in self.scheduler.snapshot()['tasks']:
                console.write('%d %s %s' % (task['id'], task['name'], task['state']))
        elif command == 'kill' and args:
            try:
                task = self.scheduler.find(int(args[0]))
                if task and task.owner is not None and task.owner != console.window.id:
                    self.scheduler.cancel(task.id)
                    console.write('Cancelled %d' % task.id)
                else:
                    console.write('Missing/protected/current task')
            except ValueError:
                console.write('Usage: kill ID')
        elif command == 'apt':
            from ok45_pkg import PackageManager
            self.start_job(console, PackageManager().command_job(args), 'apt')
        elif command == 'install' and len(args) == 1:
            from ok45_pkg import PackageManager
            self.start_job(console, PackageManager().bundle_job(args[0]), 'install')
        elif command == 'update':
            if args and args[0] != 'status':
                self.shell_launch, self.exiting = value, True
            else:
                from ok45_update import Updater
                self.start_job(console, Updater().command_job(args), 'update')
        elif command == 'updates':
            if args and args[0] == 'apply':
                self.launch('updates apply')
            else:
                from ok45_store import StoreService
                self.start_job(console, StoreService().command_job(args), 'updates')
        elif command == 'timezone':
            try:
                value = clock.set_timezone(args[0]) if args else clock.settings()
                console.write('%s %s' % (value['label'], clock.offset_text(value['offset_minutes'])))
            except Exception as error:
                console.write('Timezone: ' + str(error))
        elif command == 'echo':
            console.write(' '.join(args))
        elif command == 'clear':
            console.lines = []
            console.scroll = 0
        elif command == 'exit':
            self.close(console.window.id)
        elif command == 'reboot':
            self.shell_launch, self.exiting = 'reboot', True
        elif command == 'desktop':
            if args:
                self.launch(' '.join(args))
        else:
            from ok45_script import PROTECTED
            if command in PROTECTED and command not in ('main', 'boot', 'desktop', 'run', 'setup', 'setup2', 'NotMain'):
                path = '/' + command + '.py'
                import ok45_fs
                if ok45_fs.exists(path):
                    if command in ('demo_gfx', 'demo_3d', 'demo_text', 'edit', 'clock', 'wifi', 'sysmon', 'web'):
                        self.launch(path + (' ' + ' '.join(args) if args else ''), 'gfx')
                    else:
                        from ok45_script import run_job
                        self.start_job(console, run_job(path, console, args), command)
                else:
                    console.write('Not installed: ' + command)
            else:
                import ok45_fs
                path = '/' + command + '.py'
                if ok45_fs.exists(path) and not command.startswith('ok45_'):
                    self.launch(path + (' ' + ' '.join(args) if args else ''))
                else:
                    console.write('Unknown command; help lists available commands')
        self.changed()

    def start_job(self, console, messages, name):
        if console.running:
            messages.close()
            console.write('This window already has a running job')
            return None
        def task():
            console.running = True
            try:
                for message in messages:
                    if isinstance(message, int) and not isinstance(message, bool):
                        yield message
                        continue
                    if message:
                        console.write(message)
                    yield 0
            except Exception as error:
                console.write('Error: %s' % error)
            finally:
                close = getattr(messages, 'close', None)
                if close:
                    close()
                console.running = console.waiting = False
                console.task = None
                console.invalidate()
                if name in ('apt', 'install'):
                    self.refresh_apps()
                self.changed()
        console.running, console.stopped = True, False
        try:
            console.task = self.scheduler.spawn(name, task(), owner=console.window.id)
            return console.task
        except Exception:
            console.running = False
            messages.close()
            raise

    def input_task(self):
        while True:
            # Limit each CardKB batch; a paste cannot starve the compositor.
            for _ in range(4):
                code = self.term.readkey()
                if not code:
                    break
                try:
                    self.key(code)
                except Exception as error:
                    self.status = 'Input: ' + str(error)
                    self.changed()
            if self.exiting:
                self.request_exit()
            yield 4

    def clock_task(self):
        while True:
            self.loader.prune(self.wm.windows)
            stamp = clock.localtime()
            value = '%02d:%02d' % (stamp[3], stamp[4])
            if value != self.wm.clock:
                self.wm.clock = value
                self.wm.damage.add((176, 0, WIDTH - 176, TOP))
                self.changed()
            yield 1000

    def compositor_task(self):
        while True:
            sent = self.wm.flush(2)
            yield 0 if sent else 8

    def run(self, initial=None):
        global CURRENT
        if CURRENT is not None:
            raise RuntimeError('Desktop already running')
        CURRENT = self
        kernel.CURRENT = self.scheduler
        try:
            if initial:
                self.launch(initial)
            else:
                self.open('about')
            self.scheduler.spawn('keyboard', self.input_task())
            self.scheduler.spawn('clock-service', self.clock_task())
            self.scheduler.spawn('compositor', self.compositor_task())
            while not self.exit_requested:
                self.scheduler.step()
                delay = self.scheduler.idle_ms(8)
                if delay:
                    time.sleep_ms(delay)
        finally:
            CURRENT = None
            kernel.CURRENT = None
            self.shutdown()

    def shutdown(self):
        self.scheduler.close()
        for window in self.wm.windows:
            window.app = None
        self.wm.windows = []
        self.wm.draw_overlay = self.wm.draw_background = None
        self.wm.pending = self.wm.view = self.wm.buffer = None
        self.loader.prune(())
        gc.collect()

    def snapshot(self):
        windows = []
        for window in self.wm.windows:
            content = window.app.semantic()
            content['controls'] = window.app.controls()
            windows.append({'id': window.id, 'app': window.kind, 'title': window.title,
                            'rect': list(window.rect), 'focused': window.id == self.wm.focused,
                            'client': list(window.client()), 'controls': window.controls(),
                            'minimized': window.minimized, 'content': content})
        pointer = self.wm.pointer.snapshot()
        pointer['target'] = self.pointer_target()
        controls = [{'action': 'start', 'label': 'Start', 'rect': [3, BOTTOM + 3, 48, 16]}]
        controls.extend({'action': 'focus', 'window_id': window.id, 'label': window.title,
                         'rect': list(rect)} for window, rect in self.wm.taskbar_buttons())
        return {'active': True, 'version': VERSION, 'model_version': self.model_version,
                'status': self.status, 'input_mode': self.wm.input_mode, 'pointer': pointer,
                'controls': controls,
                'menu': {'open': self.menu, 'selected': self.menu_index,
                         'tab': self.menu_tab, 'page': self.menu_page, 'tabs': self.menu_tabs(),
                         'rect': list(self.menu_rect()), 'entries': self.menu_entries(),
                         'controls': self.menu_controls()},
                'applications': self.registry.snapshot(), 'icons': self.icon_controls(),
                'registry_errors': self.registry.errors, 'timezone': clock.settings(),
                'moving': self.moving, 'exiting': self.exiting,
                'keys_processed': self.keys_processed, 'window_limit': self.wm.limit,
                'windows': windows, 'scheduler': self.scheduler.snapshot(),
                'renderer': self.wm.snapshot()}
