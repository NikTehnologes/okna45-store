"""Interactive, backed-up Okna45 updater for a flash folder or a Pico serial port.

Select a release directory containing os-files.json. Only its verified allowlist
is copied. No recursive deletes, repo uploads or unknown-file overwrites occur.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import queue
import secrets
import sys
import threading
import time

STATE = 'system/update/host-files.json'
FORBIDDEN = ('repo', 'data', 'apps', 'scripts', 'documents')
RESERVE = 32768
STATE_PATHS = (STATE, 'system/update/system.json', 'system/update/software.json')
ASSETS = ('ok45_bootanim.oba',)


def version(value):
    if not isinstance(value, str):
        raise ValueError('Invalid OS version')
    parts = value.split('.')
    if len(parts) != 3 or any(not p or len(p) > 5 or any(ch not in '0123456789' for ch in p) for p in parts):
        raise ValueError('OS version must be major.minor.patch')
    return tuple(int(p) for p in parts)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_plan(path, value):
    temporary = path.with_name(path.name + '.new')
    with temporary.open('wb') as output:
        output.write((json.dumps(value, indent=2) + '\n').encode('utf-8'))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Invalid relative file path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Unsafe path: ' + value)
    return value


def os_path(path):
    # A single named binary asset, never arbitrary files/directories/settings.
    return '/' not in path and (path.endswith('.py') or path in ASSETS)


def release_at(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'os-files.json').read_bytes())
    version(manifest.get('version'))
    if (manifest.get('format') != 1 or manifest.get('product') != 'Okna45' or
            manifest.get('delete_unlisted') is not False or not isinstance(manifest.get('files'), list)):
        raise ValueError('Not an Okna45 allowlist, or deletion was requested')
    files = {}
    for item in manifest['files']:
        path, source = relative(item['path']), relative(item['source'])
        if not os_path(path):
            raise ValueError('OS manifest may only manage root Python modules and the named boot animation: ' + path)
        if path in files or item.get('channel') not in ('stable', 'system', 'software'):
            raise ValueError('Duplicate file or invalid channel')
        source_path = (directory / source).resolve()
        if not source_path.is_relative_to(directory) or source_path.is_symlink():
            raise ValueError('Source escapes the selected release')
        if type(item.get('size')) is not int or not 0 <= item['size'] <= 65536:
            raise ValueError('OS file size must be 0..65536 bytes')
        data = source_path.read_bytes()
        if len(data) != item['size'] or digest(data) != item['sha256']:
            raise ValueError('Release hash/size mismatch: ' + path)
        if path in ASSETS and (item['channel'] != 'system' or data[:4] != b'OBA2' or len(data) < 24):
            raise ValueError('Boot asset must be a system-channel OBA2 animation')
        files[path] = (item, data)
    if not 1 <= len(files) <= 80 or 'main.py' not in files:
        raise ValueError('Missing main.py or implausible OS manifest')
    return manifest, files


class Folder:
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        if not self.root.is_dir():
            raise ValueError('Flash directory does not exist')

    def target(self, path):
        target = (self.root / relative(path)).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError('Flash path escapes selected folder')
        return target

    def read(self, path):
        target = self.target(path)
        return target.read_bytes() if target.is_file() else None

    def hash(self, path):
        data = self.read(path)
        return digest(data) if data is not None else None

    def write(self, path, data):
        target = self.target(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.ok45-' + secrets.token_hex(4))
        try:
            with temporary.open('xb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def remove_created(self, path):
        target = self.target(path)
        if target.is_file():
            target.unlink()

    def free(self):
        import shutil
        return shutil.disk_usage(self.root).free

    def block(self):
        return 4096

    def close(self, reboot=False):
        pass


class Pico:
    """Raw REPL over serial, no mass-storage assumptions or mpremote dependency."""
    def __init__(self, port):
        try:
            import serial
        except ImportError:
            raise RuntimeError('Install pyserial: python -m pip install pyserial') from None
        self.port = serial.Serial(port, 115200, timeout=.1, write_timeout=5)
        try:
            self.port.write(b'\r\x03\x03')
            time.sleep(.15)
            self.port.reset_input_buffer()
            # Raw soft reset clears interrupted GUI references; main.py is not
            # run. Existing boot.py may perform its own recovery first.
            self.port.write(b'\r\x01')
            self.until(b'>')
            self.port.write(b'\x04')
            self.until(b'raw REPL; CTRL-B to exit\r\n>')
            self.exec("import os, json, ubinascii, uhashlib, gc\ngc.collect()")
        except BaseException:
            self.port.close()
            raise

    def until(self, end, timeout=30):
        deadline = time.monotonic() + timeout
        data = bytearray()
        while not data.endswith(end):
            if time.monotonic() >= deadline:
                raise TimeoutError('Pico did not answer raw REPL')
            chunk = self.port.read(1)
            if chunk:
                data.extend(chunk)
            elif time.monotonic() >= deadline:
                raise TimeoutError('Pico did not answer raw REPL')
            if len(data) > 2_000_000:
                raise RuntimeError('Unexpected oversized REPL output')
        return bytes(data[:-len(end)])

    def exec(self, text):
        encoded = text.encode('utf-8')
        for offset in range(0, len(encoded), 128):
            self.port.write(encoded[offset:offset + 128])
            time.sleep(.008)
        self.port.write(b'\x04')
        self.until(b'OK')
        output = self.until(b'\x04')
        error = self.until(b'\x04')
        self.until(b'>')
        if error.strip():
            raise RuntimeError(error.decode('utf-8', 'replace').strip())
        return output.decode('utf-8', 'replace').strip()

    def read(self, path):
        path = '/' + relative(path)
        size = self.exec("try:\n print(os.stat(%r)[6])\nexcept OSError:\n print(-1)" % path)
        if int(size) < 0:
            return None
        if int(size) > 131072:
            raise ValueError('Unexpected file size; refusing backup: ' + path)
        self.exec("_ok45f=open(%r,'rb')" % path)
        parts = []
        try:
            for _ in range(0, int(size), 512):
                encoded = self.exec("print(ubinascii.b2a_base64(_ok45f.read(512)).decode().strip())")
                parts.append(base64.b64decode(encoded))
        finally:
            self.exec('_ok45f.close(); _ok45f=None; gc.collect()')
        data = b''.join(parts)
        if len(data) != int(size):
            raise ValueError('Incomplete Pico backup: ' + path)
        return data

    def hash(self, path):
        path = '/' + relative(path)
        return self.exec("try:\n _f=open(%r,'rb')\nexcept OSError:\n _f=None\n"
                         "if _f is None:\n print('missing')\nelse:\n _h=uhashlib.sha256()\n"
                         " while True:\n  _b=_f.read(512)\n  if not _b: break\n  _h.update(_b)\n"
                         " _f.close()\n print(ubinascii.hexlify(_h.digest()).decode())\n"
                         "_f=_h=_b=None\ngc.collect()" % path).replace('missing', '') or None

    def write(self, path, data):
        path = '/' + relative(path)
        temporary = path + '.host-' + secrets.token_hex(4)
        parent = path.rsplit('/', 1)[0]
        self.exec("_p=''\nfor _v in %r.split('/'):\n if _v:\n  _p+='/' + _v\n"
                  "  try: os.mkdir(_p)\n  except OSError: pass\n"
                  "_ok45f=open(%r,'wb')" % (parent, temporary))
        try:
            for offset in range(0, len(data), 384):
                encoded = base64.b64encode(data[offset:offset + 384])
                self.exec('_ok45f.write(ubinascii.a2b_base64(%r))' % encoded)
            self.exec('_ok45f.flush(); _ok45f.close(); _ok45f=None')
            if self.hash(temporary[1:]) != digest(data):
                raise ValueError('Pico staging hash mismatch: ' + path)
            self.exec("os.rename(%r,%r)\nif hasattr(os,'sync'): os.sync()" % (temporary, path))
        except BaseException:
            try:
                self.exec("try: _ok45f.close()\nexcept: pass\n"
                          "try: os.remove(%r)\nexcept OSError: pass" % temporary)
            except Exception:
                pass
            raise

    def remove_created(self, path):
        self.exec("try: os.remove(%r)\nexcept OSError: pass" % ('/' + relative(path)))

    def free(self):
        return int(self.exec("_v=os.statvfs('/'); print(_v[0]*_v[3]); _v=None"))

    def block(self):
        return int(self.exec("print(os.statvfs('/')[0])"))

    def close(self, reboot=False):
        try:
            if reboot:
                self.port.write(b'import machine; machine.reset()\x04')
            else:
                self.port.write(b'\x02')
        except OSError:
            pass
        finally:
            self.port.close()


def known_releases(directory):
    """Recognize stock old OS hashes without importing any guest Python."""
    hashes = {}
    roots = [Path(directory).resolve(), Path(__file__).resolve().parents[1] / 'updates']
    for root in roots:
        for path in root.glob('**/release.json'):
            if len(path.relative_to(root).parts) > 3:
                continue
            try:
                value = json.loads(path.read_bytes())
                for entries in value.get('channels', {}).values():
                    for name, sha in entries.items():
                        hashes.setdefault(name, set()).add(sha)
                for name, sha in value.get('stable_files', {}).items():
                    hashes.setdefault(name, set()).add(sha)
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    bundled = Path(directory) / 'known-os-hashes.json'
    if bundled.is_file():
        for name, values in json.loads(bundled.read_bytes()).items():
            hashes.setdefault(name, set()).update(values)
    return hashes


def update(release, backend, backup, allow_untracked=False, log=print):
    manifest, files = release_at(release)
    backup = Path(backup).resolve()
    backup.mkdir(parents=True, exist_ok=False)
    (backup / 'release-selected.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for path in ('system/update/journal.json', 'system/pkg/journal.json'):
        if backend.hash(path) is not None:
            raise ValueError('Pending recovery journal: ' + path + '; complete recovery first')
    states = {}
    for path in STATE_PATHS:
        data = backend.read(path)
        if data is not None:
            value = json.loads(data)
            if not isinstance(value, dict) or not isinstance(value.get('files'), dict):
                raise ValueError('Corrupt ownership state kept: ' + path)
            if version(value.get('version')) > version(manifest['version']):
                raise ValueError('OS downgrade refused; keep the newer baseline: ' + path)
            states[path] = (value, data)
    known = known_releases(release)
    tracked = {}
    for state, _ in states.values():
        tracked.update(state['files'])
    changes, originals, collisions = [], {}, []
    for path, (item, data) in files.items():
        if path.endswith('.py') and backend.hash(path[:-3] + '.mpy') is not None:
            raise ValueError('Compiled .mpy shadows ' + path + '; resolve manually, nothing overwritten')
        actual = backend.hash(path)
        if actual == item['sha256']:
            continue
        if actual is not None and actual != tracked.get(path) and actual not in known.get(path, ()):
            collisions.append(path)
        changes.append(path)
    if collisions and not allow_untracked:
        raise ValueError('Unknown/locally modified OS files: ' + ', '.join(collisions) +
                         '. Back them up and explicitly allow replacement; user data are never selected.')
    for path in changes + list(STATE_PATHS):
        original = backend.read(path)
        originals[path] = original
        if original is not None:
            target = backup / 'before' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
    log('Backed up %d files to %s' % (sum(v is not None for v in originals.values()), backup))
    block = backend.block()
    if not 1 <= block <= 65536:
        raise ValueError('Invalid filesystem allocation unit')
    rounded = lambda size: (size + block - 1) // block * block
    growth = sum(max(0, rounded(len(files[path][1])) - rounded(len(originals[path] or b''))) for path in changes)
    needed = growth + max((rounded(len(files[path][1])) for path in changes), default=0) + RESERVE + rounded(16384) * 2
    if backend.free() < needed:
        raise ValueError('Not enough free flash for a file + state + 32768-byte reserve')
    channels = {name: {'version': manifest['version'], 'channel': name, 'restart_required': True,
                       'files': dict(states.get('system/update/' + name + '.json', ({'files': {}},))[0]['files'])}
                for name in ('system', 'software')}
    for path, (item, _) in files.items():
        if item['channel'] in channels:
            channels[item['channel']]['files'][path] = item['sha256']
    host = {'format': 1, 'version': manifest['version'],
            'files': {path: item['sha256'] for path, (item, _) in files.items()}}
    state_bytes = {'system/update/' + name + '.json': (json.dumps(state, separators=(',', ':')) + '\n').encode()
                   for name, state in channels.items()}
    state_bytes[STATE] = (json.dumps(host, separators=(',', ':')) + '\n').encode()
    if any(len(data) > 16384 for data in state_bytes.values()):
        raise ValueError('Update baseline exceeds the device JSON limit')
    written = []
    plan = {'version': manifest['version'], 'paths': changes, 'status': 'prepared',
            'written': written, 'before': {path: digest(data) if data is not None else None for path, data in originals.items()},
            'after': {**{path: files[path][0]['sha256'] for path in changes},
                      **{path: digest(data) for path, data in state_bytes.items()}},
            'preserved': 'Every unlisted file, including repo, data, apps, scripts, settings and notes'}
    journal = backup / 'host-update.json'
    save_plan(journal, plan)
    try:
        # main.py goes last. Recovery and existing user work are never deleted.
        for path in sorted(changes, key=lambda value: (value == 'main.py', value)):
            log('Update ' + path)
            written.append(path)
            save_plan(journal, plan)
            backend.write(path, files[path][1])
            if backend.hash(path) != files[path][0]['sha256']:
                raise ValueError('Installed hash mismatch: ' + path)
        for path, data in state_bytes.items():
            written.append(path)
            save_plan(journal, plan)
            backend.write(path, data)
            if backend.hash(path) != digest(data):
                raise ValueError('Installed baseline hash mismatch: ' + path)
    except BaseException:
        log('Interrupted/failed: restoring only files changed by this updater')
        failures = []
        for path in reversed(written):
            try:
                if originals.get(path) is None:
                    backend.remove_created(path)
                else:
                    backend.write(path, originals[path])
            except Exception as error:
                failures.append(path + ': ' + str(error))
        plan.update(status='rollback_failed' if failures else 'rolled_back', rollback_errors=failures)
        save_plan(journal, plan)
        if failures:
            log('Do not reboot: use backup/before to recover! ' + '; '.join(failures))
        raise
    plan['status'] = 'completed'
    save_plan(journal, plan)
    log('Updated to %s: %d OS files; unlisted files were not touched.' % (manifest['version'], len(changes)))
    return backup


def restore(backup, backend, allow_modified=False, log=print):
    """Restore exactly the updater's recorded paths, including after a USB loss."""
    backup = Path(backup).resolve()
    journal = backup / 'host-update.json'
    plan = json.loads(journal.read_bytes())
    for path in ('system/update/journal.json', 'system/pkg/journal.json'):
        if backend.hash(path) is not None:
            raise ValueError('Complete the on-device transaction recovery first: ' + path)
    before, after, written = plan['before'], plan['after'], plan['written']
    payloads = {}
    for path in dict.fromkeys(written):
        relative(path)
        if not (path in STATE_PATHS or os_path(path)):
            raise ValueError('Backup requests an unsafe restore path: ' + path)
        expected = before[path]
        data = None
        if expected is not None:
            source = (backup / 'before' / path).resolve()
            if not source.is_relative_to(backup):
                raise ValueError('Backup file escapes its directory')
            data = source.read_bytes()
            if digest(data) != expected:
                raise ValueError('Backup was modified/corrupted: ' + path)
        actual = backend.hash(path)
        if actual not in (before[path], after[path]) and not allow_modified:
            raise ValueError('File changed AFTER this update; keep it or explicitly allow restore: ' + path)
        payloads[path] = data
    # Restore modules/baselines first, boot entry last; never enumerate/delete
    # anything outside the recorded OS operations.
    for path in sorted(payloads, key=lambda value: (value == 'main.py', value)):
        data = payloads[path]
        log('Restore ' + path)
        if data is None:
            backend.remove_created(path)
        else:
            backend.write(path, data)
        if backend.hash(path) != before[path]:
            raise ValueError('Restore hash mismatch: ' + path)
    plan['status'] = 'restored'
    save_plan(journal, plan)
    log('Restored recorded OS files from ' + str(backup) + '; unlisted files were untouched.')


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    app = tk.Tk()
    app.title('Okna45 — безопасное обновление ОС')
    app.geometry('720x540')
    release, folder, port = tk.StringVar(), tk.StringVar(), tk.StringVar()
    mode, permit = tk.StringVar(value='pico'), tk.BooleanVar(value=False)
    body = ttk.Frame(app, padding=14)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text='1. Папка новой версии (с os-files.json)', font=('', 11, 'bold')).pack(anchor='w')
    row = ttk.Frame(body); row.pack(fill='x', pady=5)
    ttk.Entry(row, textvariable=release).pack(side='left', fill='x', expand=True)
    ttk.Button(row, text='Выбрать…', command=lambda: release.set(filedialog.askdirectory(title='Папка версии ОС') or release.get())).pack(side='right')
    ttk.Label(body, text='2. Куда обновлять', font=('', 11, 'bold')).pack(anchor='w', pady=(12, 2))
    row = ttk.Frame(body); row.pack(fill='x')
    ttk.Radiobutton(row, text='Pico через USB / COM', variable=mode, value='pico').pack(side='left')
    ports = []
    try:
        from serial.tools import list_ports
        ports = [p.device for p in list_ports.comports()]
    except ImportError:
        pass
    ttk.Combobox(row, textvariable=port, values=ports, width=16).pack(side='left', padx=10)
    if len(ports) == 1: port.set(ports[0])
    row = ttk.Frame(body); row.pack(fill='x', pady=8)
    ttk.Radiobutton(row, text='Папка флеша / эмулятора', variable=mode, value='folder').pack(side='left')
    ttk.Entry(row, textvariable=folder).pack(side='left', fill='x', expand=True)
    ttk.Button(row, text='Выбрать…', command=lambda: folder.set(filedialog.askdirectory(title='Папка флеша') or folder.get())).pack(side='right')
    ttk.Checkbutton(body, text='Разрешить замену неизвестных/изменённых ОС-файлов ПОСЛЕ backup', variable=permit).pack(anchor='w', pady=8)
    ttk.Label(body, text='repo не копируется. Неизвестные файлы, JSON-настройки, заметки и приложения не удаляются.\n'
                        'Закройте Thonny/mpremote и эмулятор. USB Pico не является диском с Python-файлами.').pack(anchor='w')
    output = tk.Text(body, height=13, state='disabled', wrap='word')
    output.pack(fill='both', expand=True, pady=10)
    events = queue.Queue()
    def append(text):
        output.configure(state='normal'); output.insert('end', text + '\n'); output.see('end'); output.configure(state='disabled')
    def start(restoring=False):
        source = filedialog.askdirectory(title='Backup с host-update.json') if restoring else release.get()
        if not source:
            return
        try:
            manifest = json.loads((Path(source) / 'host-update.json').read_bytes()) if restoring else release_at(source)[0]
        except Exception as error:
            messagebox.showerror('Ошибка папки', str(error)); return
        if mode.get() == 'pico' and not port.get():
            messagebox.showerror('COM', 'Выберите порт Pico'); return
        if not messagebox.askyesno('Подтвердите операцию', ('Восстановить ОС-файлы из backup?' if restoring else 'Обновить ОС до %s?' % manifest['version']) +
                                   '\n\nСначала сохраните открытые заметки/черновики.\nТекущая ОС на Pico будет остановлена.\n'
                                   'Заменяются только записанные ОС-файлы; repo и пользовательские данные не выбираются.'):
            return
        selected = (source, mode.get(), port.get(), folder.get(), permit.get())
        button.configure(state='disabled')
        restore_button.configure(state='disabled')
        def work():
            backend = None
            try:
                source, kind, com, destination, allow = selected
                backend = Pico(com) if kind == 'pico' else Folder(destination)
                backup = Path.home() / 'Okna45-backups' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
                if restoring:
                    restore(source, backend, allow, log=lambda value: events.put(('log', value)))
                    backup = Path(source)
                else:
                    update(source, backend, backup, allow, log=lambda value: events.put(('log', value)))
                backend.close(reboot=kind == 'pico'); backend = None
                events.put(('done', 'Готово. Backup: ' + str(backup)))
            except Exception as error:
                events.put(('error', str(error)))
            finally:
                if backend is not None:
                    backend.close(reboot=False)
        threading.Thread(target=work, daemon=False).start()
    button = ttk.Button(body, text='Обновить ОС с сохранением пользовательского', command=start)
    button.pack(fill='x')
    restore_button = ttk.Button(body, text='Восстановить только ОС-файлы из backup…', command=lambda: start(True))
    restore_button.pack(fill='x', pady=4)
    def close_window():
        if str(button['state']) == 'disabled':
            messagebox.showwarning('Операция выполняется', 'Не отключайте Pico и дождитесь завершения/отката.'); return
        app.destroy()
    app.protocol('WM_DELETE_WINDOW', close_window)
    def drain():
        try:
            while True:
                kind, text = events.get_nowait(); append(text)
                if kind in ('done', 'error'):
                    button.configure(state='normal')
                    restore_button.configure(state='normal')
                    (messagebox.showinfo if kind == 'done' else messagebox.showerror)('Okna45', text)
        except queue.Empty:
            pass
        app.after(100, drain)
    app.after(100, drain)
    app.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path)
    parser.add_argument('--restore-backup', type=Path, help='restore the exact recorded OS changes from a host backup')
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--port')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--allow-untracked', action='store_true')
    parser.add_argument('--yes', action='store_true', help='confirm the selected OS-only operation')
    args = parser.parse_args()
    if not args.release and not args.restore_backup:
        gui(); return
    if args.release and args.restore_backup:
        parser.error('Choose update OR --restore-backup')
    if bool(args.folder) == bool(args.port):
        parser.error('Choose exactly one of --folder or --port')
    label = 'Restore recorded OS files?' if args.restore_backup else 'Update Okna45 to %s?' % release_at(args.release)[0]['version']
    if not args.yes and input(label + ' [yes/no] ').strip().lower() != 'yes':
        return
    backend = Pico(args.port) if args.port else Folder(args.folder)
    success = False
    try:
        backup = args.backup or Path.home() / 'Okna45-backups' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
        if args.restore_backup:
            restore(args.restore_backup, backend, args.allow_untracked)
        else:
            update(args.release, backend, backup, args.allow_untracked)
        success = True
    finally:
        backend.close(reboot=success and bool(args.port))


if __name__ == '__main__':
    main()
