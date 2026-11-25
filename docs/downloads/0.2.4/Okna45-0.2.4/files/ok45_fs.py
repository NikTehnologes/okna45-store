"""Tiny bounded file helpers shared by desktop and package manager."""
import os
import json

_operation = None


def acquire(owner):
    global _operation
    if _operation is not None:
        raise RuntimeError('Another package/update operation is active')
    _operation = owner


def release(owner):
    global _operation
    if _operation == owner:
        _operation = None


def sync():
    function = getattr(os, 'sync', None)
    if function:
        function()


def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def directory(path):
    try:
        return bool(os.stat(path)[0] & 0x4000)
    except OSError:
        return False


def mkdirs(path):
    current = ''
    for part in path.split('/'):
        if not part:
            continue
        current += '/' + part
        if exists(current):
            if not directory(current):
                raise OSError('Not a directory: ' + current)
        else:
            os.mkdir(current)


def remove(path):
    if exists(path):
        os.remove(path)


def replace(source, destination):
    function = getattr(os, 'replace', os.rename)
    function(source, destination)


def read_text(path, limit):
    size = os.stat(path)[6]
    if size > limit:
        raise ValueError('File exceeds %d bytes: %s' % (limit, path))
    with open(path, 'rb') as file:
        # MicroPython may allocate the requested capacity BEFORE reaching EOF.
        # Never reserve 32 KiB merely to read a 23-byte script.
        data = file.read(size)
        if len(data) != size or file.read(1):
            raise ValueError('File changed while reading: ' + path)
    text = data.decode('utf-8')
    data = None
    return text


def load_json(path, limit=16384, default=None):
    if not exists(path):
        return default
    if os.stat(path)[6] > limit:
        raise ValueError('JSON exceeds %d bytes: %s' % (limit, path))
    with open(path, 'r') as file:
        return json.load(file)


def receive_job(reader, path, limit):
    mkdirs(path.rsplit('/', 1)[0])
    size = 0
    with open(path, 'wb') as file:
        while True:
            chunk = reader.read(512)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError('Catalog exceeds %d bytes' % limit)
            file.write(chunk)
            yield None
        file.flush()


def atomic_text(path, text):
    parent = path.rsplit('/', 1)[0]
    if parent:
        mkdirs(parent)
    temporary = path + '.new'
    try:
        with open(temporary, 'wb') as file:
            file.write(text.encode('utf-8'))
            file.flush()
        replace(temporary, path)
        sync()
    finally:
        remove(temporary)


def atomic_json(path, value, limit=None):
    mkdirs(path.rsplit('/', 1)[0])
    temporary = path + '.new'
    try:
        with open(temporary, 'w') as file:
            json.dump(value, file)
            file.flush()
        if limit is not None and os.stat(temporary)[6] > limit:
            raise ValueError('JSON exceeds %d bytes' % limit)
        replace(temporary, path)
        sync()
    finally:
        remove(temporary)
