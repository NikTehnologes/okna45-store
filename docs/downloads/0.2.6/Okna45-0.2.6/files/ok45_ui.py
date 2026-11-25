"""Clipped, damage-driven window compositor using one 5 KiB RGB565 stripe."""
from framebuf import FrameBuffer, RGB565

WIDTH, HEIGHT = 320, 240
STRIPE = 8
TOP, BOTTOM = 20, 220


def rgb(r, g, b):
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


TEAL = rgb(0, 112, 112)
SILVER = rgb(192, 192, 192)
LIGHT = rgb(248, 248, 240)
SHADOW = rgb(80, 80, 80)
NAVY = rgb(0, 32, 112)
BLACK = 0
WHITE = 65535
GREEN = rgb(40, 208, 128)


def intersection(a, b):
    x, y = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return (x, y, right - x, bottom - y) if right > x and bottom > y else None


def union(a, b):
    x, y = min(a[0], b[0]), min(a[1], b[1])
    return (x, y, max(a[0] + a[2], b[0] + b[2]) - x,
            max(a[1] + a[3], b[1] + b[3]) - y)


def contains(rect, x, y):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


# A tiny two-colour software pointer, painted through the same SPI compositor.
# '#' is outline, '.' is white, spaces are transparent. No saved-screen buffer.
POINTER_ROWS = ('#', '##', '#.#', '#..#', '#...#', '#....#', '#.....#',
                '#......#', '#.......#', '#....#####', '#..#.#', '#.# #.#',
                '##  #.#', '    #..#', '     #.#', '     ###')


class Pointer:
    def __init__(self, damage, x=24, y=224, step=8):
        self.damage = damage
        self.x, self.y, self.step = x, y, step
        self.visible = True

    def rect(self):
        return (self.x, self.y, 10, len(POINTER_ROWS))

    def move(self, dx, dy):
        x = max(0, min(WIDTH - 1, self.x + dx))
        y = max(0, min(HEIGHT - 1, self.y + dy))
        actual = (x - self.x, y - self.y)
        if actual != (0, 0):
            if self.visible:
                self.damage.add(self.rect())
            self.x, self.y = x, y
            if self.visible:
                self.damage.add(self.rect())
        return actual

    def show(self, visible):
        if self.visible != visible:
            self.damage.add(self.rect())
            self.visible = visible

    def draw(self, canvas):
        if not self.visible or not intersection(self.rect(), canvas.region):
            return
        for row, pixels in enumerate(POINTER_ROWS):
            if not canvas.clip or not canvas.clip[1] <= self.y + row < canvas.clip[1] + canvas.clip[3]:
                continue
            start = 0
            while start < len(pixels):
                char = pixels[start]
                end = start + 1
                while end < len(pixels) and pixels[end] == char:
                    end += 1
                if char != ' ':
                    canvas.fill((self.x + start, self.y + row, end - start, 1),
                                BLACK if char == '#' else WHITE)
                start = end

    def snapshot(self):
        return {'x': self.x, 'y': self.y, 'visible': self.visible, 'step': self.step,
                'hotspot': 'top-left', 'rect': list(self.rect())}


class Damage:
    def __init__(self, limit=8):
        self.rects = []
        self.limit = limit

    def add(self, rect):
        rect = intersection(rect, (0, 0, WIDTH, HEIGHT))
        if rect is None:
            return
        index = 0
        while index < len(self.rects):
            other = self.rects[index]
            if intersection((rect[0] - 1, rect[1] - 1, rect[2] + 2, rect[3] + 2), other):
                rect = union(rect, self.rects.pop(index))
                index = 0
            else:
                index += 1
        self.rects.append(rect)
        if len(self.rects) > self.limit:
            rect = self.rects[0]
            for other in self.rects[1:]:
                rect = union(rect, other)
            self.rects = [rect]


class Canvas:
    def __init__(self, framebuffer, region, clip=None, buffer=None):
        self.fb = framebuffer
        self.region = region
        self.clip = intersection(region, clip) if clip is not None else region
        self.origin = (region[0], region[1])
        self.buffer = buffer
        if buffer is not None and self.clip and self.clip != region:
            x, y, w, h = self.clip
            offset = ((y - region[1]) * region[2] + x - region[0]) * 2
            # A clipped VIEW of the one stripe, not a second pixel buffer.
            self.fb = FrameBuffer(buffer[offset:], w, h, RGB565, region[2])
            self.origin = (x, y)

    @staticmethod
    def color(value):
        # MicroPython framebuffer is native-endian; the SPI driver expects BE.
        return ((value & 255) << 8) | (value >> 8)

    def fill(self, rect, color):
        area = intersection(rect, self.clip) if self.clip else None
        if area:
            x, y, w, h = area
            self.fb.fill_rect(x - self.origin[0], y - self.origin[1], w, h, self.color(color))

    def text(self, x, y, text, color=BLACK):
        if self.clip is None or not intersection((x, y, len(text) * 8, 8), self.clip):
            return
        # All app text starts within its client area and is truncated to width.
        left = max(0, (self.clip[0] - x) // 8)
        right = min(len(text), (self.clip[0] + self.clip[2] - x + 7) // 8)
        if right > left:
            self.fb.text(text[left:right], x + left * 8 - self.origin[0],
                         y - self.origin[1], self.color(color))

    def line(self, x0, y0, x1, y1, color):
        if self.clip is None:
            return
        x, y, w, h = self.clip
        right, bottom = x + w - 1, y + h - 1

        def code(px, py):
            return (1 if px < x else 2 if px > right else 0) | (4 if py < y else 8 if py > bottom else 0)

        a, b = code(x0, y0), code(x1, y1)
        for _ in range(8):
            if not (a | b):
                self.fb.line(x0 - self.origin[0], y0 - self.origin[1],
                             x1 - self.origin[0], y1 - self.origin[1], self.color(color))
                return
            if a & b:
                return
            outside = a or b
            if outside & 8:
                px, py = x0 + (x1 - x0) * (bottom - y0) // (y1 - y0), bottom
            elif outside & 4:
                px, py = x0 + (x1 - x0) * (y - y0) // (y1 - y0), y
            elif outside & 2:
                px, py = right, y0 + (y1 - y0) * (right - x0) // (x1 - x0)
            else:
                px, py = x, y0 + (y1 - y0) * (x - x0) // (x1 - x0)
            if outside == a:
                x0, y0, a = px, py, code(px, py)
            else:
                x1, y1, b = px, py, code(px, py)

    def bevel(self, rect, raised=True):
        x, y, w, h = rect
        a, b = (WHITE, SHADOW) if raised else (SHADOW, WHITE)
        self.fill((x, y, w, 1), a); self.fill((x, y, 1, h), a)
        self.fill((x, y + h - 1, w, 1), b); self.fill((x + w - 1, y, 1, h), b)

    def button(self, rect, label, selected=False, enabled=True):
        self.fill(rect, NAVY if selected else SILVER)
        self.bevel(rect, not selected)
        x, y, w, h = rect
        label = label[:max(0, (w - 4) // 8)]
        self.text(x + max(2, (w - len(label) * 8) // 2), y + (h - 8) // 2,
                  label, (WHITE if selected else BLACK) if enabled else SHADOW)

    def icon(self, x, y, rows, color=NAVY, accent=GREEN):
        scale = 2 if len(rows) == 8 else 1
        if self.clip is None or not intersection((x, y, 16, 16), self.clip):
            return
        for index, row in enumerate(rows):
            for column, pixel in enumerate(row):
                if pixel != '.':
                    self.fill((x + column * scale, y + index * scale, scale, scale),
                              accent if pixel == '+' else color)


class Window:
    def __init__(self, identity, kind, title, rect):
        self.id, self.kind, self.title = identity, kind, title[:28]
        self.rect = rect
        self.minimized = False
        self.app = None

    def client(self):
        x, y, w, h = self.rect
        return (x + 4, y + 22, w - 8, h - 26)

    def controls(self):
        x, y, w, h = self.rect
        return [{'action': 'move', 'rect': [x + 3, y + 3, w - 42, 16]},
                {'action': 'minimize', 'rect': [x + w - 36, y + 5, 14, 12]},
                {'action': 'close', 'rect': [x + w - 19, y + 5, 14, 12]}]


class WindowManager:
    def __init__(self, display, limit=4):
        self.display = display
        self.limit = max(1, min(6, limit))
        self.windows = []
        self.sequence = 0
        self.focused = None
        self.damage = Damage()
        self.pointer = Pointer(self.damage)
        self.input_mode = 'pointer'
        self.buffer = bytearray(WIDTH * STRIPE * 2)
        self.view = memoryview(self.buffer)
        self.pending = None
        self.bytes_sent = 0
        self.stripes_sent = 0
        self.regions_sent = 0
        self.draw_overlay = None
        self.draw_background = None
        self.clock = '--:--'
        self.damage.add((0, 0, WIDTH, HEIGHT))

    def set_input_mode(self, mode):
        if self.input_mode != mode:
            self.input_mode = mode
            self.pointer.show(mode != 'input')
            self.damage.add((80, 0, 88, TOP))

    def taskbar_buttons(self):
        width = min(64, (WIDTH - 58) // max(1, len(self.windows)))
        return [(window, (56 + index * width, BOTTOM + 3, width - 3, 16))
                for index, window in enumerate(sorted(self.windows, key=lambda win: win.id))]

    def hit_test(self, x, y):
        if contains((3, BOTTOM + 3, 48, 16), x, y):
            return 'start', None
        for window, rect in self.taskbar_buttons():
            if contains(rect, x, y):
                return 'focus', window.id
        if y < TOP or y >= BOTTOM:
            return 'background', None
        for window in reversed(self.windows):
            if window.minimized or not contains(window.rect, x, y):
                continue
            for control in window.controls():
                if contains(control['rect'], x, y):
                    return control['action'], window.id
            return ('client' if contains(window.client(), x, y) else 'frame'), window.id
        return 'background', None

    def add(self, kind, title, rect):
        if len(self.windows) >= self.limit:
            raise RuntimeError('Window limit reached; close a window')
        self.sequence += 1
        window = Window(self.sequence, kind, title, rect)
        self.windows.append(window)
        self.focus(window.id)
        return window

    def get(self, identity=None):
        identity = self.focused if identity is None else identity
        for window in self.windows:
            if window.id == identity:
                return window
        return None

    def focus(self, identity):
        window = self.get(identity)
        if window is None:
            return False
        if self.focused == identity and not window.minimized and self.windows[-1] is window:
            return True
        old = self.get()
        if old:
            self.damage.add(old.rect)
        window.minimized = False
        self.windows.remove(window)
        self.windows.append(window)
        self.focused = identity
        self.damage.add(window.rect)
        self.damage.add((0, BOTTOM, WIDTH, HEIGHT - BOTTOM))
        return True

    def cycle(self):
        ids = sorted(window.id for window in self.windows)
        if ids:
            index = ids.index(self.focused) if self.focused in ids else -1
            self.focus(ids[(index + 1) % len(ids)])

    def close(self, identity):
        window = self.get(identity)
        if window is None:
            return False
        self.damage.add(window.rect)
        self.windows.remove(window)
        if self.focused == identity:
            self.focused = None
            visible = [w for w in self.windows if not w.minimized]
            if visible:
                self.focus(visible[-1].id)
        self.damage.add((0, BOTTOM, WIDTH, HEIGHT - BOTTOM))
        return True

    def minimize(self, identity=None):
        window = self.get(identity)
        if window:
            window.minimized = True
            self.damage.add(window.rect)
            visible = [w for w in self.windows if not w.minimized]
            self.focused = None
            if visible:
                self.focus(visible[-1].id)
            self.damage.add((0, BOTTOM, WIDTH, HEIGHT - BOTTOM))

    def move(self, dx, dy):
        window = self.get()
        if window:
            x, y, w, h = window.rect
            self.damage.add(window.rect)
            window.rect = (max(0, min(WIDTH - w, x + dx)),
                           max(TOP, min(BOTTOM - h, y + dy)), w, h)
            self.damage.add(window.rect)
            return window.rect[0] - x, window.rect[1] - y
        return 0, 0

    def invalidate(self, window, rect=None):
        if not window.minimized:
            self.damage.add(rect or window.client())

    def draw(self, canvas):
        canvas.fill((0, 0, WIDTH, HEIGHT), TEAL)
        canvas.fill((0, 0, WIDTH, TOP), NAVY)
        canvas.text(8, 6, 'Okna45', WHITE)
        canvas.text(80, 6, {'pointer': 'Tab Input', 'input': 'Tab Point',
                           'move': 'Enter Drop'}[self.input_mode], WHITE)
        canvas.text(176, 6, 'Pico W ' + self.clock, WHITE)
        # Wallpaper is cheap text/vector composition, not a stored image.
        canvas.text(12, 192, 'Okna45 / RP2040', rgb(104, 176, 176))
        canvas.text(12, 204, 'Arrows move / Enter click', rgb(104, 176, 176))
        if self.draw_background:
            self.draw_background(canvas)
        for window in self.windows:
            if window.minimized or not intersection(window.rect, canvas.region):
                continue
            x, y, w, h = window.rect
            canvas.fill(window.rect, SILVER)
            canvas.bevel(window.rect)
            canvas.fill((x + 3, y + 3, w - 6, 16), NAVY if window.id == self.focused else SHADOW)
            title = window.title[:max(0, (w - 50) // 8)]
            canvas.text(x + 7, y + 7, title, WHITE)
            for control, text in zip(window.controls()[1:], ('_', 'X')):
                canvas.button(control['rect'], text)
            client = window.client()
            if window.app and intersection(client, canvas.region):
                window.app.draw(Canvas(canvas.fb, canvas.region, client, canvas.buffer), client)
        canvas.fill((0, BOTTOM, WIDTH, HEIGHT - BOTTOM), SILVER)
        canvas.bevel((0, BOTTOM, WIDTH, HEIGHT - BOTTOM))
        canvas.button((3, BOTTOM + 3, 48, 16), 'Start')
        for window, rect in self.taskbar_buttons():
            canvas.button(rect, window.title, window.id == self.focused)
        if self.draw_overlay:
            self.draw_overlay(canvas)
        self.pointer.draw(canvas)

    def flush(self, max_stripes=4):
        """Bound each repaint slice so keyboard/tasks run between SPI batches."""
        sent = 0
        while sent < max_stripes:
            if self.pending is None:
                if not self.damage.rects:
                    break
                x, y, w, h = self.damage.rects.pop(0)
                fb = FrameBuffer(self.buffer, w, STRIPE, RGB565)
                self.pending = [x, y, w, y + h, fb]
                self.regions_sent += 1
            x, y, w, bottom, fb = self.pending
            height = min(STRIPE, bottom - y)
            canvas = Canvas(fb, (x, y, w, height), buffer=self.view)
            self.draw(canvas)
            size = w * height * 2
            self.display.block(x, y, x + w - 1, y + height - 1, self.view[:size])
            self.bytes_sent += size
            self.stripes_sent += 1
            sent += 1
            self.pending[1] += height
            if self.pending[1] >= bottom:
                self.pending = None
        return sent

    def snapshot(self):
        return {'buffer_bytes': len(self.buffer), 'bytes_sent': self.bytes_sent,
                'stripes_sent': self.stripes_sent, 'regions_sent': self.regions_sent,
                'pending': len(self.damage.rects) + (1 if self.pending else 0),
                'full_framebuffer': False}
