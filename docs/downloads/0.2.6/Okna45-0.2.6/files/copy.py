def run(term, args):
    if len(args) < 2: term.write("Usage: copy <src> <dst>\n"); return
    try:
        with open(args[0], "rb") as fs: data = fs.read()
        with open(args[1], "wb") as fd: fd.write(data)
        term.write("Copied %d B\n" % len(data))
    except OSError as e: term.write("copy: %s\n" % e)


