"""Time-selected boot GIF tiles. One 5120-byte stripe; no GIF frame directory.

Artwork is compiled on the computer without removing/repainting source frames.
Native 512-byte-window DEFLATE expands independent base/sparse tile states.
All resources close before the graphical desktop is imported.
"""
import io
import os
import struct
import time

STRIPE_BYTES = 5120


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
            if (magic != b'OBA1' or (width, height) != (320, 240) or not 1 <= tw <= 160 or
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
            self.states = self._read(self.frames * dynamic * 2)
            self.chunks = self._read(chunks * 8)
            self.dynamic = dynamic
            self.last = bytearray(b'\xff\xff' * dynamic)
            self.buffer = bytearray(STRIPE_BYTES)
            self.view = memoryview(self.buffer)
            self.decoder = decoder or native_decoder()
            self.payload_start = 24 + metadata_size
            self.file_size = os.stat(path)[6]
        except BaseException:
            self.file.close()
            raise

    def _read(self, size):
        value = self.file.read(size)
        if len(value) != size:
            raise ValueError('Truncated boot animation')
        return value

    def _chunk(self, identity, destination):
        if not 0 <= identity < len(self.chunks) // 8:
            raise ValueError('Invalid boot chunk identity')
        offset, size, expanded = struct.unpack_from('<IHH', self.chunks, identity * 8)
        if (offset < self.payload_start or not 0 < size <= 4096 or offset + size > self.file_size or
                expanded != len(destination)):
            raise ValueError('Invalid boot chunk bounds')
        self.file.seek(offset)
        source = io.BytesIO(self._read(size))
        inflater = self.decoder(source)
        try:
            written = inflater.readinto(destination)
            if written != expanded:
                raise ValueError('Truncated boot tile pixels')
        finally:
            inflater.close()
            source.close()

    def initial(self, display):
        """Paint one complete base image before starting the five-cycle clock."""
        for offset in range(0, len(self.tiles), 16):
            x, y, w, h, base, first, count, slot = struct.unpack_from('<8H', self.tiles, offset)
            size = w * h * 2
            if w > 160 or h > 8 or x + w > 320 or y + h > 240 or not size:
                raise ValueError('Boot tile outside display')
            self._chunk(base, self.view[:size])
            display.block(x, y, x + w - 1, y + h - 1, self.view[:size])
            if slot != 65535:
                if slot >= self.dynamic:
                    raise ValueError('Invalid boot tile slot')
                state = struct.unpack_from('<H', self.states, slot * 2)[0]
                struct.pack_into('<H', self.last, slot * 2, state)

    def render(self, display, index, expired=None):
        """Independent target state: skipped/reversed frames cannot leave trails."""
        if not 0 <= index < self.frames:
            raise ValueError('Invalid animation frame')
        for offset in range(0, len(self.tiles), 16):
            x, y, w, h, base, first, count, slot = struct.unpack_from('<8H', self.tiles, offset)
            if slot == 65535:
                continue
            if expired is not None and expired():
                return False
            identity = struct.unpack_from('<H', self.states, (index * self.dynamic + slot) * 2)[0]
            if identity == struct.unpack_from('<H', self.last, slot * 2)[0]:
                continue
            size, patch_size = w * h * 2, 0
            for mask in range(first, first + count):
                start, length = struct.unpack_from('<HH', self.masks, mask * 4)
                if start + length > size or not length or (start | length) & 1:
                    raise ValueError('Invalid sparse boot pixels')
                patch_size += length
            if size + patch_size > STRIPE_BYTES:
                raise ValueError('Boot tile would exceed the single stripe')
            self._chunk(base, self.view[:size])
            self._chunk(identity, self.view[size:size + patch_size])
            source = size
            for mask in range(first, first + count):
                start, length = struct.unpack_from('<HH', self.masks, mask * 4)
                self.view[start:start + length] = self.view[source:source + length]
                source += length
            # Do not send an already expired frame after decompression.
            if expired is not None and expired():
                return False
            display.block(x, y, x + w - 1, y + h - 1, self.view[:size])
            struct.pack_into('<H', self.last, slot * 2, identity)
        return True

    def close(self):
        self.file.close()
        self.view = self.buffer = self.tiles = self.masks = self.states = self.chunks = self.last = None
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
                'frame_queue': False, 'buffer_bytes': STRIPE_BYTES}
