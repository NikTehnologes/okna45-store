"""Stable update recovery v1; no imports of files a system update may replace."""
import os
import json


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _remove(path):
    if _exists(path):
        os.remove(path)


def _sync():
    function = getattr(os, 'sync', None)
    if function:
        function()


def recover(root='/system/update', database=None):
    """Rollback uncommitted rename transactions, or finish committed cleanup."""
    journal_path, stage = root + '/journal.json', root + '/stage'
    if not _exists(journal_path):
        return False
    with open(journal_path, 'rb') as file:
        content = file.read(65537)
    if len(content) > 65536:
        raise ValueError('Recovery journal exceeds limit')
    journal = json.loads(content.decode())
    if not isinstance(journal, dict):
        raise ValueError('Invalid recovery journal')
    # A shared update journal may belong to the OTHER update channel.
    # Older package journals have no database field; only those use the fallback.
    database = journal.get('database', database)
    allowed = ('/system/update/system.json', '/system/update/software.json') if root == '/system/update' else (
        '/system/pkg/installed.json',) if root == '/system/pkg' else ()
    if database not in allowed:
        raise ValueError('Unsafe recovery database')
    if not isinstance(journal.get('before'), dict):
        raise ValueError('Invalid pre-update database')
    entries = journal.get('entries')
    if not isinstance(entries, list) or len(entries) > 128:
        raise ValueError('Invalid recovery entries')
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError('Invalid recovery entry')
        path = item.get('path', '')
        if (item.get('id') != index or not isinstance(path, str) or not path or
                path.startswith('/') or '\\' in path or
                any(part in ('', '.', '..') for part in path.split('/')) or
                any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-' for ch in path) or
                not isinstance(item.get('had'), bool)):
            raise ValueError('Unsafe recovery entry')
    if journal.get('phase') not in ('prepared', 'committed'):
        raise ValueError('Invalid recovery phase')
    if journal['phase'] != 'committed':
        # Reverse order also supports main.py being the final installed file.
        for item in reversed(entries):
            target, backup = '/' + item['path'], stage + '/back-%d' % item['id']
            if _exists(backup):
                _remove(target)
                os.rename(backup, target)
            elif not item['had']:
                _remove(target)
        temporary = database + '.new'
        with open(temporary, 'w') as file:
            file.write(json.dumps(journal['before']))
            file.flush()
        # RP2 LittleFS supports rename replacement; avoid an unlink gap.
        getattr(os, 'replace', os.rename)(temporary, database)
        _sync()
    if _exists(stage):
        for name in os.listdir(stage):
            tail = name.rsplit('-', 1)[-1]
            if (name.startswith('new-') or name.startswith('back-')) and tail and all('0' <= ch <= '9' for ch in tail):
                _remove(stage + '/' + name)
    _remove(journal_path)
    _sync()
    return True


def mark_boot():
    for channel in ('system', 'software'):
        path = '/system/update/' + channel + '.json'
        if not _exists(path):
            continue
        with open(path, 'rb') as file:
            content = file.read(16385)
        if len(content) > 16384:
            raise ValueError('Update state exceeds limit')
        value = json.loads(content.decode())
        if not isinstance(value, dict):
            raise ValueError('Invalid update state')
        if value.get('restart_required'):
            value['restart_required'] = False
            with open(path + '.new', 'w') as file:
                file.write(json.dumps(value))
                file.flush()
            getattr(os, 'replace', os.rename)(path + '.new', path)
            _sync()
