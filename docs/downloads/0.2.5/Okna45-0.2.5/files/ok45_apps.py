"""Built-in source store. The loader reads one marked block, never imports all."""

#@app about
from ok45_api import Application as App
class About(App):
    title = 'Welcome'
    def semantic(self):
        return {'lines': ['Okna45 0.2.4 / Pico W', 'Graphical boot. Real SPI.',
                          'Arrows: move pointer', 'Enter: click',
                          'Tab: pointer / app input', 'Click title: move window',
                          'Enter again: drop window', 'X close / _ minimize',
                          '~: Start in pointer mode', 'Esc: pointer / Start']}
#@end


#@app clock
import ok45_time as clock
from ok45_api import Application as App
class Clock(App):
    title = 'Clock'
    def __init__(self, desktop, window):
        super().__init__(desktop, window)
        self.status = 'UTC RTC / fixed offset'
        self.value = self.read()

    def read(self):
        now = clock.localtime()
        return ('%02d:%02d:%02d' % (now[3], now[4], now[5]),
                '%04d-%02d-%02d' % now[:3], clock.settings()['label'])

    def tick(self):
        value = self.read()
        if value != self.value:
            self.value = value
            self.invalidate()
        return False

    def semantic(self):
        value = clock.settings()
        return {'timezone': value, 'status': self.status,
                'lines': [self.value[0], self.value[1], value['label'],
                          clock.offset_text(value['offset_minutes']), 'RTC UTC; no automatic DST', self.status]}

    def controls(self):
        return self.toolbar((('zone', 'Zone'), ('minus', '-15m'), ('plus', '+15m'), ('sync', 'Sync')))

    def activate(self, control):
        try:
            value = clock.settings()
            if control['action'] == 'sync':
                clock.sync()
                self.status = 'NTP synced / UTC'
            elif control['action'] == 'zone':
                labels = [label for label, offset in clock.PRESETS]
                index = labels.index(value['label']) + 1 if value['label'] in labels else 0
                clock.set_timezone(labels[index % len(labels)])
                self.status = 'Timezone saved'
            else:
                offset = max(-720, min(840, value['offset_minutes'] +
                             (-15 if control['action'] == 'minus' else 15)))
                clock.set_timezone(offset)
                self.status = 'Timezone saved'
            self.value = self.read()
        except Exception as error:
            self.status = str(error)
        self.invalidate()
#@end


#@app monitor
import gc
from ok45_api import Application as App
from ok45_ui import SHADOW, GREEN
class Monitor(App):
    title = 'System'
    def __init__(self, desktop, window):
        super().__init__(desktop, window)
        self.ram = -1
        self.tick()

    def tick(self):
        ram = gc.mem_free() // 1024
        if ram != self.ram:
            self.ram = ram
            self.invalidate()
        return False

    def semantic(self):
        return {'lines': ['Free heap: %d KiB' % self.ram,
                           'Tasks: %d / %d' % (len(self.desktop.scheduler.tasks), self.desktop.scheduler.limit),
                           'Paint buffer: 5 KiB', 'CPU: cooperative tasks',
                          'Tasks: button below']}

    def controls(self):
        return self.toolbar((('tasks', 'Tasks'),))

    def activate(self, control):
        self.desktop.open('tasks')

    def draw(self, canvas, rect):
        super().draw(canvas, rect)
        x, y, w, h = rect
        by = y + min(70, h - 12)
        canvas.fill((x + 4, by, w - 8, 8), SHADOW)
        canvas.fill((x + 4, by, max(0, min(w - 8, (w - 8) * self.ram // 264)), 8), GREEN)
#@end


#@app files
import os
import ok45_fs as fs
from ok45_api import Application as App, UP, DOWN
from ok45_ui import WHITE, BLACK, NAVY, SILVER
class Files(App):
    title = 'Files'
    def __init__(self, desktop, window):
        super().__init__(desktop, window)
        self.path = '/'
        self.entries = []
        self.selected = 0
        self.scroll = 0
        self.status = 'Choose file; Open button'
        self.refresh()

    def refresh(self):
        try:
            self.entries = sorted(os.listdir(self.path))[:128]
            self.status = 'Open: view / Run: execute'
        except OSError as error:
            self.entries = []
            self.status = str(error)
        self.selected = min(self.selected, max(0, len(self.entries) - 1))
        self.scroll = max(0, self.selected - self.visible_rows() + 1)
        self.invalidate()

    def key(self, code):
        if code in (UP, DOWN):
            self.selected = max(0, min(len(self.entries) - 1, self.selected + (-1 if code == UP else 1)))
            rows = self.visible_rows()
            self.scroll = max(0, min(self.scroll, self.selected))
            if self.selected >= self.scroll + rows:
                self.scroll = self.selected - rows + 1
        elif code in (8, 127):
            self.path = self.path.rsplit('/', 1)[0] or '/'
            self.selected = 0
            self.refresh()
        elif code in (10, 13) and self.entries:
            self.open_selected()
        elif code in (ord('r'), ord('R')):
            self.refresh()
        self.invalidate()

    def visible_rows(self):
        return max(1, (self.window.client()[3] - 50) // 10)

    def open_selected(self, execute=False):
        if not self.entries:
            return
        path = self.path.rstrip('/') + '/' + self.entries[self.selected]
        try:
            if fs.directory(path):
                self.path, self.selected = path, 0
                self.refresh()
            elif execute or path.endswith('.sin'):
                window = self.desktop.launch('install ' + path if path.endswith('.sin') else path)
                self.status = 'Opened ' + path if window else self.desktop.status
            else:
                window = self.desktop.open('notes', path=path)
                self.status = 'Opened ' + path if window else self.desktop.status
        except Exception as error:
            self.status = 'Open: ' + str(error)
        self.invalidate()

    def controls(self):
        controls = self.toolbar((('parent', 'Up'), ('refresh', 'Load'),
                                 ('prev', '^'), ('next', 'v'), ('open', 'Open'), ('run', 'Run')))
        controls[-2]['enabled'] = bool(self.entries)
        controls[-1]['enabled'] = bool(self.entries)
        x, y, w, h = self.window.client()
        controls.extend({'action': 'select', 'label': name, 'index': self.scroll + row,
                         'button': False, 'rect': [x + 2, y + 16 + row * 10, w - 4, 10]}
                        for row, name in enumerate(self.entries[self.scroll:self.scroll + self.visible_rows()]))
        return controls

    def activate(self, control):
        action = control['action']
        if action == 'select':
            self.selected = control['index']
            self.invalidate()
        elif action == 'refresh':
            self.refresh()
        elif action == 'run':
            self.open_selected(True)
        else:
            self.key({'parent': 8, 'prev': UP, 'next': DOWN, 'open': 13}[action])

    def semantic(self):
        return {'path': self.path, 'selected': self.selected,
                'scroll': self.scroll, 'status': self.status,
                'entries': self.entries,
                'lines': [self.path] + self.entries[self.scroll:self.scroll + self.visible_rows()]}

    def draw(self, canvas, rect):
        canvas.fill(rect, WHITE)
        x, y, w, h = rect
        canvas.text(x + 3, y + 3, self.path[:(w - 6) // 8])
        rows = self.visible_rows()
        for row, name in enumerate(self.entries[self.scroll:self.scroll + rows]):
            selected = self.scroll + row == self.selected
            ry = y + 17 + row * 10
            canvas.fill((x + 2, ry - 1, w - 4, 10), NAVY if selected else WHITE)
            canvas.text(x + 4, ry, name[:(w - 8) // 8], WHITE if selected else BLACK)
        canvas.fill((x, y + h - 34, w, 34), SILVER)
        canvas.text(x + 2, y + h - 31, self.status[:(w - 4) // 8])
        self.draw_controls(canvas)
#@end


#@app notes
import ok45_fs as fs
from ok45_api import Application as App, LEFT, UP, DOWN, RIGHT
from ok45_kernel import ticks_ms, ticks_diff
from ok45_ui import WHITE, BLACK, SILVER, SHADOW, contains
MAX_NOTE = 8192
class Notes(App):
    title = 'Notes'
    interval_ms = 100
    def __init__(self, desktop, window, path='/notes.txt'):
        super().__init__(desktop, window)
        from ok45_script import file_path, editable
        self.path, self.content, self.cursor = file_path(path), '', 0
        path = self.path
        self.dirty = False
        self.confirm = False
        self.scroll = 0
        self.horizontal = 0
        self.caret_on = True
        self.caret_tick = ticks_ms()
        self.readonly = not editable(path)
        self.file_dialog = None
        self.filename = ''
        self.pending_action = None
        self.status = 'Tab input; Save button below'
        try:
            if fs.exists(path):
                self.content = fs.read_text(path, MAX_NOTE).replace('\r\n', '\n').replace('\r', '\n')
            if any(ord(char) > 126 or (ord(char) < 32 and char not in '\n\t\r') for char in self.content):
                self.readonly = True
                self.status = 'Non-ASCII preview / read only'
        except Exception as error:
            self.readonly = True
            self.status = str(error)
        if self.readonly and self.status.startswith('Tab'):
            self.status = 'Protected preview / read only'
        window.title = path.rsplit('/', 1)[-1][:28]

    def save(self):
        if self.readonly:
            self.status = 'Read only'
            self.invalidate()
            return False
        try:
            fs.atomic_text(self.path, self.content)
        except Exception as error:
            self.status = 'Save: ' + str(error)
            self.invalidate()
            return False
        else:
            self.dirty = self.confirm = False
            self.status = 'Saved ' + self.path
        self.invalidate()
        return not self.dirty

    def close(self):
        if self.file_dialog:
            self.cancel_dialog()
            return False
        if self.dirty:
            self.confirm = True
            self.status = 'Y save / N discard / Esc back'
            self.invalidate()
            return False
        return True

    def key(self, code):
        if self.file_dialog:
            if code == 27:
                self.cancel_dialog()
            elif code in (8, 127):
                self.filename = self.filename[:-1]
            elif code in (10, 13):
                self.finish_file_dialog()
            elif 32 <= code <= 126 and len(self.filename) < 100:
                self.filename += chr(code)
            self.invalidate()
            return
        if self.confirm:
            if code in (ord('y'), ord('Y')):
                self.save()
                if not self.dirty:
                    self.finish_pending()
            elif code in (ord('n'), ord('N')):
                if self.pending_action:
                    try:
                        self.content = (fs.read_text(self.path, MAX_NOTE) if fs.exists(self.path) else '')
                        self.cursor = self.scroll = self.horizontal = 0
                    except Exception as error:
                        self.status = 'Discard: ' + str(error)
                        self.invalidate()
                        return
                self.dirty = self.confirm = False
                self.finish_pending()
            elif code == 27:
                self.confirm = False
                self.desktop.exiting = False
                self.desktop.shell_launch = None
                self.pending_action = None
                self.status = 'Close cancelled'
                self.invalidate()
            return
        self.caret_on = True
        self.caret_tick = ticks_ms()
        if code == LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif code == RIGHT:
            self.cursor = min(len(self.content), self.cursor + 1)
        elif code in (UP, DOWN):
            start = self.content.rfind('\n', 0, self.cursor) + 1
            column = self.cursor - start
            if code == UP and start:
                previous = self.content.rfind('\n', 0, start - 1) + 1
                self.cursor = min(start - 1, previous + column)
            elif code == DOWN:
                end = self.content.find('\n', self.cursor)
                if end >= 0:
                    following = self.content.find('\n', end + 1)
                    self.cursor = min(len(self.content) if following < 0 else following, end + 1 + column)
        elif not self.readonly:
            if code in (8, 127) and self.cursor:
                self.content = self.content[:self.cursor - 1] + self.content[self.cursor:]
                self.cursor -= 1
                self.dirty = True
            elif code in (10, 13) or 32 <= code <= 126:
                if len(self.content) >= MAX_NOTE:
                    self.status = 'Note limit: 8192 bytes'
                else:
                    char = '\n' if code in (10, 13) else chr(code)
                    self.content = self.content[:self.cursor] + char + self.content[self.cursor:]
                    self.cursor += 1
                    self.dirty = True
        row = self.content.count('\n', 0, self.cursor)
        visible = self.visible_rows()
        self.scroll = min(self.scroll, row)
        if row >= self.scroll + visible:
            self.scroll = row - visible + 1
        self.ensure_horizontal()
        self.invalidate()

    def visible_rows(self):
        return max(1, (self.window.client()[3] - 58) // 10)

    def cancel_dialog(self):
        self.confirm = False
        self.file_dialog = self.pending_action = None
        self.desktop.exiting = False
        self.desktop.shell_launch = None
        self.status = 'Cancelled'
        self.desktop.set_mode('pointer')
        self.invalidate()

    def begin_file_dialog(self, action):
        if action in ('new', 'open') and self.dirty:
            self.pending_action = action
            self.close()
            self.desktop.set_mode('pointer')
            return
        self.file_dialog = action
        self.filename = '' if action == 'new' else self.path
        self.confirm = True
        self.status = 'Type a path; Enter confirms'
        self.desktop.set_mode('input')
        self.invalidate()

    def finish_pending(self):
        action, self.pending_action = self.pending_action, None
        if action:
            self.begin_file_dialog(action)
        else:
            self.desktop.close(self.window.id)

    def finish_file_dialog(self):
        from ok45_script import file_path, editable
        try:
            path = file_path(self.filename)
            action = self.file_dialog
            if action in ('new', 'save_as') and not editable(path):
                raise ValueError('Protected path; choose /scripts/ or /documents/')
            if action in ('new', 'save_as') and fs.exists(path) and path != self.path:
                raise ValueError('File exists; Open it or choose a new name')
            if action == 'new' and fs.exists(path):
                raise ValueError('File exists; use Open')
            if action == 'save_as':
                fs.atomic_text(path, self.content)
                self.path, self.readonly, self.dirty = path, False, False
            else:
                content = (fs.read_text(path, MAX_NOTE).replace('\r\n', '\n').replace('\r', '\n')
                           if action == 'open' else '')
                if action == 'open' and not fs.exists(path):
                    raise ValueError('File does not exist; use New')
                self.path, self.content, self.cursor = path, content, 0
                self.readonly = not editable(path) or any(ord(c) > 126 or
                    (ord(c) < 32 and c not in '\n\t\r') for c in content)
                self.dirty = action == 'new'  # Save can create even an empty file.
                self.scroll = self.horizontal = 0
            self.window.title = path.rsplit('/', 1)[-1][:28]
            self.file_dialog, self.confirm = None, False
            self.status = ('New; Save creates file' if action == 'new' else
                           'Opened ' + path if action == 'open' else 'Saved ' + path)
            self.desktop.set_mode('input' if action == 'new' else 'pointer')
        except Exception as error:
            self.status = str(error)
        self.invalidate()

    def ensure_horizontal(self):
        columns = max(1, (self.window.client()[2] - 8) // 8)
        start = self.content.rfind('\n', 0, self.cursor) + 1
        column = self.cursor - start
        self.horizontal = min(self.horizontal, column)
        if column >= self.horizontal + columns:
            self.horizontal = column - columns + 1

    def caret(self):
        x, y, w, h = self.window.client()
        row = self.content.count('\n', 0, self.cursor)
        start = self.content.rfind('\n', 0, self.cursor) + 1
        column = self.cursor - start
        active = self.window.id == self.desktop.wm.focused and not self.window.minimized and not self.confirm
        editing = active and self.desktop.wm.input_mode == 'input'
        return {'row': row, 'column': column, 'scroll_row': self.scroll,
                'scroll_column': self.horizontal, 'editing': editing,
                'visible': active and (not editing or self.caret_on),
                'rect': [x + 3 + (column - self.horizontal) * 8,
                         y + 2 + (row - self.scroll) * 10, 2, 10]}

    def mode_changed(self):
        self.caret_on = True
        self.caret_tick = ticks_ms()
        self.invalidate()

    def tick(self):
        if self.caret()['editing'] and ticks_diff(ticks_ms(), self.caret_tick) >= 500:
            self.caret_tick = ticks_ms()
            self.caret_on = not self.caret_on
            self.invalidate(tuple(self.caret()['rect']))
        return False

    def dialog_rect(self):
        x, y, w, h = self.window.client()
        return (x + 6, y + (h - 84) // 2, w - 12, 84)

    def controls(self):
        if self.file_dialog:
            x, y, w, h = self.dialog_rect()
            return [{'action': 'filename', 'label': 'Path', 'button': False,
                     'rect': [x + 8, y + 21, w - 16, 18]},
                    {'action': 'file_ok', 'label': 'OK', 'rect': [x + 8, y + h - 24, (w - 19) // 2, 18]},
                    {'action': 'cancel', 'label': 'Cancel', 'rect': [x + 11 + (w - 19) // 2, y + h - 24, (w - 19) // 2, 18]}]
        if not self.confirm:
            x, y, w, h = self.window.client()
            width = (w - 10) // 3
            controls = [{'action': action, 'label': label, 'enabled': True,
                         'rect': [x + 2 + (index % 3) * (width + 3),
                                  y + h - 40 + (index // 3) * 20, width, 18]}
                        for index, (action, label) in enumerate((('new', 'New'), ('open', 'Open'),
                            ('save_as', 'Save As'), ('save', 'Save'), ('run', 'Run'), ('input', 'Input')))]
            controls[3]['enabled'] = not self.readonly
            controls[4]['enabled'] = self.path.endswith('.py') and not self.readonly
            return controls
        x, y, w, h = self.dialog_rect()
        width = (w - 16 - 6) // 3
        return [{'action': action, 'label': label, 'enabled': True,
                 'rect': [x + 8 + index * (width + 3), y + h - 24, width, 18]}
                for index, (action, label) in enumerate((('save_close', 'Save'),
                                                         ('discard', 'Discard'), ('cancel', 'Cancel')))]

    def activate(self, control):
        action = control['action']
        if action in ('new', 'open', 'save_as'):
            self.begin_file_dialog(action)
        elif action == 'filename':
            self.desktop.set_mode('input')
        elif action == 'file_ok':
            self.finish_file_dialog()
        elif action == 'run':
            if self.save():
                try:
                    self.desktop.launch(self.path)
                except Exception as error:
                    self.status = 'Run: ' + str(error)
                    self.invalidate()
        elif action == 'input':
            self.desktop.set_mode('input')
        elif action == 'save':
            self.save()
        else:
            self.key({'save_close': ord('y'), 'discard': ord('n'), 'cancel': 27}[action])

    def click(self, px, py):
        if super().click(px, py):
            return True
        if self.confirm:
            return True
        x, y, w, h = self.window.client()
        if contains((x + 2, y + 2, w - 4, self.visible_rows() * 10), px, py):
            lines = self.content.split('\n')
            row = min(len(lines) - 1, self.scroll + max(0, (py - y - 3) // 10))
            column = min(len(lines[row]), max(0, (px - x - 4) // 8) + self.horizontal)
            self.cursor = sum(len(line) + 1 for line in lines[:row]) + column
            self.ensure_horizontal()
            self.desktop.set_mode('input')
            self.invalidate()
            return True
        return False

    def semantic(self):
        lines = self.content.split('\n')
        return {'path': self.path, 'dirty': self.dirty, 'read_only': self.readonly,
                 'cursor': self.cursor, 'caret': self.caret(), 'confirm_save': self.confirm,
                'dialog': self.file_dialog or ('Save changes?' if self.confirm else None),
                'filename': self.filename if self.file_dialog else None,
                'lines': lines[self.scroll:self.scroll + 12], 'status': self.status}

    def draw(self, canvas, rect):
        canvas.fill(rect, WHITE)
        x, y, w, h = rect
        lines = self.content.split('\n')
        columns = max(1, (w - 8) // 8)
        horizontal = self.horizontal
        for index, line in enumerate(lines[self.scroll:self.scroll + self.visible_rows()]):
            canvas.text(x + 4, y + 3 + index * 10, line[horizontal:horizontal + columns])
        caret = self.caret()
        if caret['visible']:
            canvas.fill(caret['rect'], BLACK if caret['editing'] and not self.readonly else SHADOW)
        canvas.fill((x, y + h - 54, w, 54), SILVER)
        status = ('* ' if self.dirty else '') + self.status
        canvas.text(x + 2, y + h - 51, status[:(w - 4) // 8])
        if self.confirm:
            dx, dy, dw, dh = self.dialog_rect()
            canvas.fill((dx, dy, dw, dh), SILVER)
            canvas.bevel((dx, dy, dw, dh))
            heading = {'new': 'New file', 'open': 'Open file', 'save_as': 'Save As'}.get(self.file_dialog, 'Save changes?')
            canvas.text(dx + 8, dy + 7, heading)
            if self.file_dialog:
                canvas.fill((dx + 8, dy + 21, dw - 16, 18), WHITE)
                canvas.text(dx + 10, dy + 26, (self.filename + '_')[-max(1, (dw - 20) // 8):])
            else:
                canvas.text(dx + 8, dy + 21, self.path[:(dw - 16) // 8])
            canvas.text(dx + 8, dy + 43, self.status[:(dw - 16) // 8])
        self.draw_controls(canvas)
#@end


#@app tasks
from ok45_api import Application as App, UP, DOWN
from ok45_ui import WHITE, BLACK, LIGHT, NAVY, SILVER
class Tasks(App):
    title = 'Tasks'
    def __init__(self, desktop, window):
        super().__init__(desktop, window)
        self.selected = 0
        self.scroll = 0
        self.status = 'System services are protected'

    def tick(self):
        self.selected = min(self.selected, max(0, len(self.desktop.scheduler.tasks) - 1))
        self.scroll = min(self.scroll, self.selected)
        self.invalidate()
        return False

    def key(self, code):
        tasks = self.desktop.scheduler.tasks
        if code in (UP, DOWN):
            self.selected = max(0, min(len(tasks) - 1, self.selected + (-1 if code == UP else 1)))
        elif tasks:
            task = tasks[min(self.selected, len(tasks) - 1)]
            if task.owner is not None:
                if code in (8, 127):
                    self.desktop.scheduler.cancel(task.id)
                elif code in (ord('p'), ord('P')):
                    self.desktop.scheduler.pause(task.id, task.state != 'paused')
        self.selected = min(self.selected, max(0, len(tasks) - 1))
        self.scroll = min(self.scroll, self.selected)
        if self.selected >= self.scroll + self.visible_rows():
            self.scroll = self.selected - self.visible_rows() + 1
        self.invalidate()

    def visible_rows(self):
        return max(1, (self.window.client()[3] - 50) // 10)

    def controls(self):
        tasks = self.desktop.scheduler.tasks
        task = tasks[min(self.selected, len(tasks) - 1)] if tasks else None
        controls = self.toolbar((('prev', '^'), ('next', 'v'),
                                 ('pause', 'Resume' if task and task.state == 'paused' else 'Pause'),
                                 ('cancel', 'Cancel')))
        for control in controls[2:]:
            control['enabled'] = task is not None and task.owner is not None
        x, y, w, h = self.window.client()
        controls.extend({'action': 'select', 'task_id': task.id, 'label': task.name,
                         'button': False, 'rect': [x + 2, y + 16 + row * 10, w - 4, 10]}
                        for row, task in enumerate(tasks[self.scroll:self.scroll + self.visible_rows()]))
        return controls

    def activate(self, control):
        action = control['action']
        if action == 'select':
            for index, task in enumerate(self.desktop.scheduler.tasks):
                if task.id == control['task_id']:
                    self.selected = index
                    break
            self.invalidate()
        else:
            self.key({'prev': UP, 'next': DOWN, 'pause': ord('p'), 'cancel': 127}[action])

    def semantic(self):
        tasks = self.desktop.scheduler.snapshot()['tasks']
        return {'tasks': tasks, 'selected': self.selected, 'scroll': self.scroll, 'status': self.status,
                'lines': ['Cooperative (yield required)'] + [
                    '%d %s %s' % (task['id'], task['name'], task['state']) for task in tasks]}

    def draw(self, canvas, rect):
        canvas.fill(rect, LIGHT)
        x, y, w, h = rect
        canvas.text(x + 4, y + 3, 'Cooperative tasks')
        tasks = self.desktop.scheduler.tasks
        for row, task in enumerate(tasks[self.scroll:self.scroll + self.visible_rows()]):
            selected = self.scroll + row == self.selected
            ry = y + 17 + row * 10
            canvas.fill((x + 2, ry - 1, w - 4, 10), NAVY if selected else LIGHT)
            line = '%d %s %s' % (task.id, task.name, task.state)
            canvas.text(x + 4, ry, line[:(w - 8) // 8], WHITE if selected else BLACK)
        canvas.fill((x, y + h - 34, w, 34), SILVER)
        canvas.text(x + 2, y + h - 31, self.status[:(w - 4) // 8])
        self.draw_controls(canvas)
#@end


#@app console
from ok45_api import Application as App, LEFT, UP, DOWN, RIGHT
from ok45_ui import BLACK, GREEN, WHITE
import gc
import sys
class Console(App):
    title = 'Console'
    def __init__(self, desktop, window, path=None):
        super().__init__(desktop, window)
        self.lines = (['Package manager', 'apt update', 'apt search', 'apt install counter', 'install /app.sin',
                       'Trusted sources only'] if window.kind == 'packages' else ['Okna45 console / help'])
        self.buffer = ''
        self.running = False
        self.scroll = 0
        self.script, self.task = path, None
        self.keys = []
        self.waiting = self.stopped = False
        self.answer = None
        self.status = 'Ready'
        self.partial = False
        self.d = desktop.term.d
        self.text = self
        self.display_mode = 'term'
        if path:
            self.lines = []
            window.title = path.rsplit('/', 1)[-1][:28]

    def start_script(self, args=None):
        if self.running or not self.script:
            return
        self.running, self.stopped, self.status = True, False, 'Running'
        self.keys, self.buffer = [], ''
        self.partial = False
        try:
            self.task = self.desktop.scheduler.spawn('script-' + str(self.window.id),
                         self.script_job(args or []), owner=self.window.id)
        except Exception:
            self.running, self.task = False, None
            raise
        self.invalidate()

    def script_job(self, args):
        job = None
        try:
            # Let the compositor show the new window BEFORE executing Python.
            yield 40
            from ok45_script import run_job
            job = run_job(self.script, self, args)
            for delay in job:
                if self.stopped:
                    break
                yield delay
            self.status = 'Stopped' if self.stopped else 'Finished'
        except EOFError:
            self.status = 'Stopped'
        except Exception as error:
            self.status = type(error).__name__
            self.write('Error: %s: %s\n' % (type(error).__name__, error))
            printer = getattr(sys, 'print_exception', None)
            if printer:
                printer(error)
        finally:
            try:
                if job is not None:
                    job.close()
            finally:
                self.running = self.waiting = False
                self.task = None
                gc.collect()
                self.invalidate()

    def stop(self):
        self.stopped, self.answer = True, None
        self.waiting = False
        task = self.desktop.scheduler.find(self.task)
        if task and task.state != 'running':
            self.desktop.scheduler.cancel(self.task)
            self.task, self.running = None, False
        self.status = 'Stopped' if not self.running else 'Stopping at next yield/input'
        self.invalidate()

    def close(self):
        self.stop()
        return not self.running

    def putc(self, text):
        self.write(text)

    def puts(self, text):
        self.write(text)

    def clear(self, **options):
        self.lines, self.scroll = [], 0
        self.invalidate()

    def cursor(self, visible):
        pass

    def attr(self, **options):
        pass

    def readkey(self):
        if self.stopped:
            raise EOFError('Stopped')
        return self.keys.pop(0) if self.keys else 0

    def input_line(self, prompt=''):
        import time
        self.write(prompt)
        self.buffer, self.answer = '', None
        self.waiting = True
        self.desktop.wm.focus(self.window.id)
        self.desktop.set_mode('input')
        self.invalidate()
        # A blocking input() cooperatively pumps the other tasks, excluding this
        # running task. Plain CPU loops still require the author to yield.
        while self.waiting and not self.stopped:
            task = self.desktop.scheduler.find(self.task)
            if task is not None and task.cancel_requested:
                self.stopped = True
                break
            self.desktop.scheduler.step()
            sleeper = getattr(time, 'sleep_ms', None)
            sleeper(4) if sleeper else time.sleep(.004)
        if self.stopped:
            raise EOFError('Stopped')
        result, self.answer = self.answer, None
        return result

    def write(self, text):
        if self.script:
            return self.write_stream(text)
        added = [line[:512] for line in str(text)[:4096].split('\n')]
        if added and not added[-1]:
            added.pop()
        columns = max(1, (self.window.client()[2] - 8) // 8)
        count = sum(max(1, (len(line) + columns - 1) // columns) for line in added)
        self.lines.extend(added)
        self.lines = self.lines[-64:]
        while sum(len(line) + 1 for line in self.lines) > 8192:
            del self.lines[0]
        if self.scroll:
            self.scroll = min(self.max_scroll(), self.scroll + count)
        self.invalidate()

    def write_stream(self, text):
        text = str(text)[:4096]
        if not text:
            return
        old = len(self.lines)
        parts = text.split('\n')
        if self.partial and self.lines:
            parts[0] = self.lines.pop() + parts[0]
        self.partial = not text.endswith('\n')
        if not self.partial:
            parts.pop()
        self.lines.extend(line[:512] for line in parts)
        self.lines = self.lines[-64:]
        while sum(len(line) + 1 for line in self.lines) > 8192:
            del self.lines[0]
        if self.scroll:
            self.scroll = min(self.max_scroll(), self.scroll + max(0, len(self.lines) - old))
        self.invalidate()

    def key(self, code):
        if code in (UP, DOWN, LEFT, RIGHT):
            delta = -1 if code in (DOWN, RIGHT) else 1
            self.scroll = max(0, min(self.max_scroll(), self.scroll + delta *
                              (self.visible_rows() if code in (LEFT, RIGHT) else 1)))
            self.invalidate()
            return
        if self.running and not self.waiting:
            if len(self.keys) < 64:
                self.keys.append(code)
            return
        if code in (8, 127):
            self.buffer = self.buffer[:-1]
        elif code in (10, 13):
            if self.waiting:
                self.answer, self.waiting = self.buffer, False
                self.write(self.buffer + '\n')
                self.buffer = ''
                return
            self.scroll = 0
            value = self.buffer.strip()
            self.buffer = ''
            if value:
                self.write('> ' + value)
                if not self.script:
                    self.desktop.console_command(self, value)
        elif 32 <= code <= 126 and len(self.buffer) < 160:
            self.buffer += chr(code)
        self.invalidate()

    def semantic(self):
        return {'buffer': self.buffer, 'busy': self.running, 'scroll': self.scroll,
                'script': self.script, 'waiting_input': self.waiting, 'status': self.status,
                'max_scroll': self.max_scroll(), 'history_lines': len(self.lines), 'lines': self.view()}

    def wrapped(self):
        columns = max(1, (self.window.client()[2] - 8) // 8)
        result = []
        for line in self.lines:
            result.extend([line[i:i + columns] for i in range(0, len(line), columns)] or [''])
        return result

    def visible_rows(self):
        return max(1, (self.window.client()[3] - 42) // 10)

    def max_scroll(self):
        return max(0, len(self.wrapped()) - self.visible_rows())

    def view(self):
        wrapped = self.wrapped()
        self.scroll = min(self.scroll, max(0, len(wrapped) - self.visible_rows()))
        end = len(wrapped) - self.scroll
        return wrapped[max(0, end - self.visible_rows()):end]

    def controls(self):
        if self.script:
            return self.toolbar((('prev', '^'), ('next', 'v'), ('end', 'End'), ('input', 'Input'),
                                  ('stop', 'Stop') if self.running else ('again', 'Again')))
        return self.toolbar((('prev', '^'), ('next', 'v'), ('end', 'End'), ('input', 'Input'), ('clear', 'Clear')))

    def activate(self, control):
        if control['action'] in ('prev', 'next'):
            self.key(UP if control['action'] == 'prev' else DOWN)
        elif control['action'] == 'end':
            self.scroll = 0
            self.invalidate()
        elif control['action'] == 'input':
            self.desktop.set_mode('input')
        elif control['action'] == 'stop':
            self.stop()
        elif control['action'] == 'again':
            self.start_script()
        else:
            self.lines = []
            self.scroll = 0
            self.invalidate()

    def draw(self, canvas, rect):
        canvas.fill(rect, BLACK)
        x, y, w, h = rect
        columns = max(1, (w - 8) // 8)
        for row, line in enumerate(self.view()):
            canvas.text(x + 4, y + 3 + row * 10, line, GREEN)
        prompt = 'History +%d; End: latest' % self.scroll if self.scroll else (
            '> ' + self.buffer if self.waiting or not self.script and not self.running else self.status)
        if (self.waiting or not self.running) and self.desktop.wm.input_mode == 'input':
            prompt += '_'
        canvas.text(x + 4, y + h - 31, prompt[-columns:], WHITE)
        self.draw_controls(canvas)
#@end


#@app cube
from ok45_api import Application as App
from ok45_ui import BLACK, GREEN
class Cube(App):
    title = 'Cube'
    VERTICES = ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))
    EDGES = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))

    def __init__(self, desktop, window):
        super().__init__(desktop, window)
        self.angle, self.points, self.paused, self.frames = 0, [], False, 0
        self.tick()

    def key(self, code):
        if code == 32:
            self.paused = not self.paused
            self.invalidate()

    def controls(self):
        return self.toolbar((('pause', 'Resume' if self.paused else 'Pause'),))

    def activate(self, control):
        self.key(32)

    def moved(self, dx, dy):
        self.points = [(x + dx, y + dy) for x, y in self.points]
        self.invalidate()

    def tick(self):
        if self.paused:
            return False
        import math
        self.angle += 0.06
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        cb, sb = math.cos(self.angle * .7), math.sin(self.angle * .7)
        x, y, w, h = self.window.client()
        scale = min(w, h - 28) * .9
        points = []
        for vx, vy, vz in self.VERTICES:
            rx, rz = vx * ca + vz * sa, -vx * sa + vz * ca
            ry, rz = vy * cb - rz * sb, vy * sb + rz * cb
            distance = rz + 4
            points.append((int(x + w / 2 + rx * scale / distance),
                            int(y + (h - 28) / 2 - ry * scale / distance)))
        self.points = points
        self.frames += 1
        self.invalidate()
        return False

    def semantic(self):
        return {'frames': self.frames, 'paused': self.paused,
                'lines': ['Cube / Pause button', 'Paused' if self.paused else 'Running']}

    def draw(self, canvas, rect):
        canvas.fill(rect, BLACK)
        for a, b in self.EDGES:
            canvas.line(self.points[a][0], self.points[a][1], self.points[b][0], self.points[b][1], GREEN)
        self.draw_controls(canvas)
#@end
