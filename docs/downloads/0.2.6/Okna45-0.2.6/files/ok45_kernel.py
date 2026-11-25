"""Small cooperative task kernel for MicroPython. No CPython thread dependency."""
import time

MAX_TASKS = 16
CURRENT = None


def ticks_ms():
    function = getattr(time, 'ticks_ms', None)
    return function() if function else int(time.monotonic() * 1000) & 0x3fffffff


def ticks_add(value, delta):
    function = getattr(time, 'ticks_add', None)
    return function(value, delta) if function else (value + delta) & 0x3fffffff


def ticks_diff(a, b):
    function = getattr(time, 'ticks_diff', None)
    return function(a, b) if function else ((a - b + 0x20000000) & 0x3fffffff) - 0x20000000


class Task:
    def __init__(self, identity, name, iterator, owner, now):
        self.id = identity
        self.name = name[:32]
        self.iterator = iterator
        self.owner = owner
        self.state = 'ready'
        self.wake = now
        self.runs = 0
        self.max_step_ms = 0
        self.error = None
        self.cancel_requested = False
        self.pause_requested = False


class Scheduler:
    """Each ready generator runs once per round and yields a delay in ms.

    A task must yield; this is not preemptive threading. A blocking socket or
    an infinite next() blocks the device. Exceptions isolate ordinary tasks.
    """
    def __init__(self, now=ticks_ms, add=ticks_add, diff=ticks_diff, limit=MAX_TASKS):
        self.now, self.add, self.diff = now, add, diff
        self.limit = limit
        self.tasks = []
        self.history = []
        self.sequence = 0
        self.rounds = 0

    def spawn(self, name, iterator, owner=None):
        if len(self.tasks) >= self.limit:
            raise RuntimeError('Task limit reached')
        if not hasattr(iterator, '__next__'):
            raise TypeError('Task must be a generator/iterator')
        self.sequence += 1
        task = Task(self.sequence, name, iterator, owner, self.now())
        self.tasks.append(task)
        return task.id

    def find(self, identity):
        for task in self.tasks:
            if task.id == identity:
                return task
        return None

    def _finish(self, task, state, error=None):
        task.state, task.error = state, error
        if task in self.tasks:
            self.tasks.remove(task)
        self.history.append(self._info(task))
        self.history = self.history[-8:]

    def cancel(self, identity):
        task = self.find(identity)
        if task is None:
            return False
        if task.state == 'running':
            task.cancel_requested = True
            return True
        try:
            close = getattr(task.iterator, 'close', None)
            if close:
                close()
        except Exception as error:
            self._finish(task, 'failed', str(error)[:160])
        else:
            self._finish(task, 'cancelled')
        return True

    def cancel_owner(self, owner):
        for task in self.tasks[:]:
            if task.owner == owner:
                self.cancel(task.id)

    def pause(self, identity, paused=True):
        task = self.find(identity)
        if task is None:
            return False
        task.pause_requested = bool(paused)
        if task.state == 'running':
            return True
        task.state = 'paused' if paused else 'ready'
        if not paused:
            task.wake = self.now()
        return True

    def step(self):
        self.rounds += 1
        count = 0
        for task in self.tasks[:]:
            if task not in self.tasks or task.state in ('paused', 'running'):
                continue
            started = self.now()
            if self.diff(started, task.wake) < 0:
                task.state = 'sleeping'
                continue
            task.state = 'running'
            try:
                delay = next(task.iterator)
                if delay is None:
                    delay = 0
                if isinstance(delay, bool) or not isinstance(delay, int) or not 0 <= delay <= 86400000:
                    raise ValueError('Task must yield a delay in 0..86400000 ms')
            except StopIteration:
                self._finish(task, 'done')
            except Exception as error:
                self._finish(task, 'failed', '%s: %s' % (type(error).__name__, error))
            else:
                task.wake = self.add(self.now(), delay)
                task.state = 'paused' if task.pause_requested else ('sleeping' if delay else 'ready')
                if task.cancel_requested:
                    self.cancel(task.id)
            task.runs += 1
            task.max_step_ms = max(task.max_step_ms, max(0, self.diff(self.now(), started)))
            count += 1
        return count

    def idle_ms(self, maximum=8):
        now = self.now()
        delay = maximum
        for task in self.tasks:
            if task.state != 'paused':
                delay = min(delay, max(0, self.diff(task.wake, now)))
        return delay

    def close(self):
        for task in self.tasks[:]:
            self.cancel(task.id)

    @staticmethod
    def _info(task):
        return {'id': task.id, 'name': task.name, 'owner': task.owner,
                'state': task.state, 'runs': task.runs,
                'max_step_ms': task.max_step_ms, 'error': task.error}

    def snapshot(self):
        return {'model': 'cooperative generators, not preemptive threads',
                'rounds': self.rounds, 'limit': self.limit,
                'tasks': [self._info(task) for task in self.tasks],
                'recent': self.history[:]}
