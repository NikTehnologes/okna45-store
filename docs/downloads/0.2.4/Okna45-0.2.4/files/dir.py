import os
def run(term, args):
    path = args[0] if args else "."
    try:
        entries = sorted(os.listdir(path))
    except OSError as e:
        term.write("dir: %s\n" % e); return
    total = 0
    for name in entries:
        full = (path.rstrip("/") + "/" + name) if path != "." else name
        try:
            st = os.stat(full); size = st[6]; is_dir = (st[0] & 0x4000) != 0
        except OSError:
            size = 0; is_dir = False
        term.write("%7d  %s%s\n" % (size, name, "/" if is_dir else ""))
        total += size
    term.write("--- %d entries, %d bytes\n" % (len(entries), total))


