"""Time-selected RGB332 boot patches. One 2560-byte buffer; no framebuffer.

Artwork is compiled on the computer without resizing/removing source frames.
Native 512-byte-window DEFLATE expands independent base/sparse tile states.
Only a selected index row is resident; chunk tables are read from flash.
ILI9341 GRAM retains the base; only changed horizontal runs reach the display.
Two sparse states share the buffer; 160 dirty-map bytes survive conversion.
All resources close before the graphical desktop is imported.
"""
import io
import os
import struct
import time

STRIPE_BYTES = 2560

try:
    from micropython import native
except ImportError:
    def native(function):
        return function


def palette332():
    output = bytearray(512)
    for index in range(256):
        r, g, b = ((index >> 5) * 255 + 3) // 7, (((index >> 2) & 7) * 255 + 3) // 7, (index & 3) * 85
        color = ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)
        output[index * 2], output[index * 2 + 1] = color >> 8, color & 255
    return output


@native
def expand332(buffer, pixels, palette):
    # Descending order is essential: output shares the input memory.
    for index in range(pixels - 1, -1, -1):
        color = buffer[index] * 2
        buffer[index * 2] = palette[color]
        buffer[index * 2 + 1] = palette[color + 1]


@native
def changed332(buffer, pixels, dirty):
    for index in range((pixels + 7) // 8):
        dirty[index] = 0
    count = 0
    for index in range(pixels):
        if buffer[index] != buffer[pixels + index]:
            dirty[index >> 3] |= 1 << (index & 7)
            count += 1
    return count


def native_decoder():
    try:
        import deflate
        return lambda stream: deflate.DeflateIO(stream, deflate.RAW, 9)
    except ImportError:
        from uzlib import DecompIO
        return lambda stream: DecompIO(stream, -9)


def frame_at(ends, elapsed):
    """Binary search original cumulative GIF delays, not a fixed FPS counter."""
    left, right = 0, len(ends) // 2
    while left < right:
        middle = (left + right) // 2
        end = struct.unpack_from('<H', ends, middle * 2)[0]
        if elapsed < end:
            right = middle
        else:
            left = middle + 1
    return left


class Animation:
    def __init__(self, path='/ok45_bootanim.oba', decoder=None):
        self.file = open(path, 'rb')
        try:
            header = struct.unpack('<4s8HI', self._read(24))
            magic, width, height, tw, th, self.frames, count, dynamic, masks, chunks = header
            if (magic != b'OBA2' or (width, height) != (320, 240) or not 1 <= tw <= 160 or
                    not 1 <= th <= 8 or not 1 <= self.frames <= 512 or
                    not 1 <= count <= 240 or not 0 <= dynamic <= count or
                    not 0 <= masks <= 8192 or not 1 <= chunks <= 4096):
                raise ValueError('Invalid bounded boot animation header')
            metadata_size = self.frames * 2 + count * 16 + masks * 4 + self.frames * dynamic * 2 + chunks * 8
            if metadata_size > 32768:
                raise ValueError('Boot animation index exceeds RAM limit')
            self.ends = self._read(self.frames * 2)
            self.period = struct.unpack_from('<H', self.ends, (self.frames - 1) * 2)[0]
            previous = 0
            for index in range(self.frames):
                end = struct.unpack_from('<H', self.ends, index * 2)[0]
                if end <= previous:
                    raise ValueError('Invalid original GIF delays')
                previous = end
            self.tiles = self._read(count * 16)
            self.masks = self._read(masks * 4)
            self.states_offset = self.file.tell()
            self.chunks_offset = self.states_offset + self.frames * dynamic * 2
            self.states = bytearray(dynamic * 2)
            self.chunk_count = chunks
            self.dynamic = dynamic
            self.last = bytearray(b'\xff\xff' * dynamic)
            self.buffer = bytearray(STRIPE_BYTES)
            self.view = memoryview(self.buffer)
            self.palette = palette332()
            self.dirty = bytearray(STRIPE_BYTES // 16)
            self.cursor = 0
            self.updates = self.changed_pixels = self.rectangles = 0
            self.decoder = decoder or native_decoder()
            self.payload_start = 24 + metadata_size
            self.file_size = os.stat(path)[6]
            if self.payload_start >= self.file_size:
                raise ValueError('Truncated boot animation tables')
        except BaseException:
            self.file.close()
            raise

    def _read(self, size):
        value = self.file.read(size)
        if len(value) != size:
            raise ValueError('Truncated boot animation')
        return value

    def _chunk(self, identity, destination):
        if not 0 <= identity < self.chunk_count:
            raise ValueError('Invalid boot chunk identity')
        self.file.seek(self.chunks_offset + identity * 8)
        offset, size, expanded = struct.unpack('<IHH', self._read(8))
        if (offset < self.payload_start or not 0 < size <= 4096 or offset + size > self.file_size or
                expanded != len(destination)):
            raise ValueError('Invalid boot chunk bounds')
        self.file.seek(offset)
        source = io.BytesIO(self._read(size))
        inflater = self.decoder(source)
        try:
            written = 0
            while written < expanded:
                count = inflater.readinto(destination[written:])
                if not count:
                    raise ValueError('Truncated boot tile pixels')
                written += count
        finally:
            close = getattr(inflater, 'close', None)
            if close:
                close()
            source.close()

    def _state(self, index):
        self.file.seek(self.states_offset + index * self.dynamic * 2)
        if self.file.readinto(self.states) != len(self.states):
            raise ValueError('Truncated boot frame index')

    def initial(self, display):
        """Paint one complete base image before starting the five-cycle clock."""
        self._state(0)
        for offset in range(0, len(self.tiles), 16):
            x, y, w, h, base, first, count, slot = struct.unpack_from('<8H', self.tiles, offset)
            pixels = w * h
            size = pixels * 2
            if w > 160 or h > 8 or x + w > 320 or y + h > 240 or not pixels:
                raise ValueError('Boot tile outside display')
            self._chunk(base, self.view[:pixels])
            expand332(self.buffer, pixels, self.palette)
            display.block(x, y, x + w - 1, y + h - 1, self.view[:size])
            if slot != 65535:
                if slot >= self.dynamic:
                    raise ValueError('Invalid boot tile slot')
                state = struct.unpack_from('<H', self.states, slot * 2)[0]
                struct.pack_into('<H', self.last, slot * 2, state)

    def render(self, display, index, expired=None):
        """Compare independent states; finish one prepared tile even if late.

        Discarding work after decode can starve every update on a slow Pico.
        Deadlines stop only between committed tiles, and the cursor rotates so
        early tiles cannot monopolize every time-selected frame.
        """
        if not 0 <= index < self.frames:
            raise ValueError('Invalid animation frame')
        self._state(index)
        beginning = self.cursor
        for step in range(0, len(self.tiles), 16):
            offset = (beginning + step) % len(self.tiles)
            x, y, w, h, base, first, count, slot = struct.unpack_from('<8H', self.tiles, offset)
            if slot == 65535:
                continue
            identity = struct.unpack_from('<H', self.states, slot * 2)[0]
            previous = struct.unpack_from('<H', self.last, slot * 2)[0]
            if identity == previous:
                continue
            pixels, patch_size = w * h, 0
            if first + count > len(self.masks) // 4:
                raise ValueError('Invalid sparse boot mask table')
            for mask in range(first, first + count):
                start, length = struct.unpack_from('<HH', self.masks, mask * 4)
                if start + length > pixels or not length:
                    raise ValueError('Invalid sparse boot pixels')
                patch_size += length
            if not patch_size or patch_size * 2 > STRIPE_BYTES:
                raise ValueError('Boot tile would exceed the single stripe')
            # Each sparse state includes original values for pixels to restore;
            # no base decompression or LCD readback is needed after initial().
            self._chunk(identity, self.view[:patch_size])
            self._chunk(previous, self.view[patch_size:patch_size * 2])
            changed = changed332(self.buffer, patch_size, self.dirty)
            expand332(self.buffer, patch_size, self.palette)
            self._send_changes(display, x, y, w, first, count)
            struct.pack_into('<H', self.last, slot * 2, identity)
            self.cursor = (offset + 16) % len(self.tiles)
            self.updates += 1
            self.changed_pixels += changed
            if expired is not None and expired():
                return False
        return True

    def _send_changes(self, display, x, y, width, first, count):
        source = 0
        for mask in range(first, first + count):
            start, length = struct.unpack_from('<HH', self.masks, mask * 4)
            while length:
                row, column = divmod(start, width)
                span = min(length, width - column)
                offset = 0
                while offset < span:
                    while offset < span and not (self.dirty[(source + offset) >> 3] & (1 << ((source + offset) & 7))):
                        offset += 1
                    begin = offset
                    while offset < span and (self.dirty[(source + offset) >> 3] & (1 << ((source + offset) & 7))):
                        offset += 1
                    if begin != offset:
                        display.block(x + column + begin, y + row, x + column + offset - 1, y + row,
                                      self.view[(source + begin) * 2:(source + offset) * 2])
                        self.rectangles += 1
                start += span
                length -= span
                source += span

    def close(self):
        self.file.close()
        self.file = self.view = self.buffer = self.palette = self.dirty = self.ends = self.tiles = self.masks = self.states = self.last = None
        self.decoder = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def play(display, path='/ok45_bootanim.oba', repeats=5):
    """Dedicated boot playback; wall-clock deadlines, never a catch-up queue."""
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError('Invalid boot repeat count')
    ticks, difference, sleep = time.ticks_ms, time.ticks_diff, time.sleep_ms
    with Animation(path) as animation:
        animation.initial(display)
        started = ticks()
        total = animation.period * repeats
        current_end = [0]

        def expired():
            return difference(ticks(), started) >= current_end[0]

        while True:
            elapsed = difference(ticks(), started)
            if elapsed >= total:
                break
            cycle, phase = divmod(elapsed, animation.period)
            index = frame_at(animation.ends, phase)
            current_end[0] = cycle * animation.period + struct.unpack_from('<H', animation.ends, index * 2)[0]
            if not animation.render(display, index, expired):
                continue
            remaining = current_end[0] - difference(ticks(), started)
            if remaining > 0:
                sleep(remaining)
        return {'frames': animation.frames, 'repeats': repeats, 'timeline_ms': total,
                'elapsed_ms': difference(ticks(), started), 'nominal_fps': 50,
                'frame_queue': False, 'buffer_bytes': STRIPE_BYTES,
                'dirty_bits_bytes': len(animation.dirty), 'updated_tiles': animation.updates,
                'changed_pixels': animation.changed_pixels, 'sent_rectangles': animation.rectangles}
