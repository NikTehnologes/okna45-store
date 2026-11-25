"""SIN1: bounded JSON manifest + concatenated SHA256-verified file payloads."""
import json
import hashlib
import binascii
import struct
import ok45_fs as fs

MAX_HEADER = 16384
MAX_FILE = 65536
MAX_TOTAL = 393216


def safe_relative(path):
    return (isinstance(path, str) and 1 <= len(path) <= 100 and not path.startswith('/') and
            all(part not in ('', '.', '..') for part in path.split('/')) and
            all(ch in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-' for ch in path))


def version_key(value):
    if not isinstance(value, str):
        raise ValueError('Version must be a string')
    parts = value.split('.')
    if len(parts) != 3 or any(not part or len(part) > 5 or any(ch not in '0123456789' for ch in part) for part in parts):
        raise ValueError('Version must be major.minor.patch')
    return tuple(int(part) for part in parts)


def digest(hasher):
    return binascii.hexlify(hasher.digest()).decode()


def file_hash(path):
    hasher = hashlib.sha256()
    with open(path, 'rb') as file:
        while True:
            chunk = file.read(512)
            if not chunk:
                break
            hasher.update(chunk)
    return digest(hasher)


def validate_file(item, limit=MAX_FILE):
    if not isinstance(item, dict) or not safe_relative(item.get('path')):
        raise ValueError('Unsafe bundle file path')
    size, sha256 = item.get('size'), item.get('sha256')
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= limit:
        raise ValueError('Invalid declared file size')
    if (not isinstance(sha256, str) or len(sha256) != 64 or
            any(ch not in '0123456789abcdef' for ch in sha256)):
        raise ValueError('SHA256 is required for every file')


class Bundle:
    def __init__(self, path):
        self.file = open(path, 'rb')
        try:
            prefix = self.read_exact(8)
            if prefix[:4] != b'SIN1':
                raise ValueError('Not a SIN1 bundle (Python installers are not executed)')
            size = struct.unpack('<I', prefix[4:])[0]
            if not 1 <= size <= MAX_HEADER:
                raise ValueError('SIN manifest exceeds limit')
            self.header = json.loads(self.read_exact(size).decode('utf-8'))
            if (not isinstance(self.header, dict) or isinstance(self.header.get('format'), bool) or
                    self.header.get('format') != 1):
                raise ValueError('SIN format must be 1')
            if self.header.get('kind') not in ('system', 'software'):
                raise ValueError('SIN kind must be system or software')
            self.remaining = 0
        except BaseException:
            self.file.close()
            raise

    def read_exact(self, size):
        value = bytearray()
        while len(value) < size:
            chunk = self.file.read(size - len(value))
            if not chunk:
                raise ValueError('Truncated SIN bundle')
            value.extend(chunk)
        return bytes(value)

    def stage_job(self, item, destination=None):
        """Always verify skipped payloads as well; never trust header alone."""
        validate_file(item)
        hasher, remaining = hashlib.sha256(), item['size']
        file = open(destination, 'wb') if destination else None
        try:
            while remaining:
                chunk = self.file.read(min(512, remaining))
                if not chunk:
                    raise ValueError('Truncated payload: ' + item['path'])
                remaining -= len(chunk)
                hasher.update(chunk)
                if file:
                    file.write(chunk)
                yield None
            if file:
                file.flush()
        finally:
            if file:
                file.close()
        if digest(hasher) != item['sha256']:
            raise ValueError('Integrity check failed: ' + item['path'])

    def finish(self):
        if self.file.read(1):
            raise ValueError('Unexpected trailing payload in SIN bundle')

    def close(self):
        self.file.close()
