"""Shared recoverable rename transaction; downloads finish before commit."""
import os
import ok45_fs as fs
from ok45_boot import recover as boot_recover


class Transaction:
    def __init__(self, root, database):
        self.root, self.database = root, database
        self.stage = root + '/stage'
        self.journal = root + '/journal.json'

    def cleanup(self):
        if fs.exists(self.stage):
            for name in os.listdir(self.stage):
                tail = name.rsplit('-', 1)[-1]
                if (name.startswith('new-') or name.startswith('back-')) and tail and all('0' <= ch <= '9' for ch in tail):
                    fs.remove(self.stage + '/' + name)
        fs.remove(self.journal)
        fs.sync()

    def recover(self):
        if fs.exists(self.journal):
            boot_recover(self.root, self.database)
        elif fs.exists(self.stage):
            self.cleanup()

    def prepare(self, required_bytes=0, file_sizes=None):
        self.recover()
        statvfs = getattr(os, 'statvfs', None)
        if statvfs:
            stat = statvfs('/')
            block = stat[1] or stat[0]
            allocation = (sum((size + block - 1) // block * block for size in file_sizes)
                          if file_sizes is not None else required_bytes)
            if block * stat[4] < allocation + 32768:
                raise OSError('Not enough flash for staging and recovery journal')
        fs.mkdirs(self.stage)

    def commit(self, entries, before, after):
        if len(entries) > 128:
            raise ValueError('Transaction file limit is 128')
        journal = {'phase': 'prepared', 'entries': entries, 'before': before, 'database': self.database}
        fs.atomic_json(self.journal, journal)
        for item in entries:
            target = '/' + item['path']
            fs.mkdirs(target.rsplit('/', 1)[0])
            if item['had']:
                fs.replace(target, self.stage + '/back-%d' % item['id'])
            if item.get('install'):
                fs.replace(self.stage + '/new-%d' % item['id'], target)
            fs.sync()
        fs.atomic_json(self.database, after)
        journal['phase'] = 'committed'
        fs.atomic_json(self.journal, journal)
        self.cleanup()
