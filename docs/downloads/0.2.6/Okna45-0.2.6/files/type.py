def run(term, args):
    if not args: term.write("Usage: type <file>\n"); return
    try:
        with open(args[0]) as f:
            for i, line in enumerate(f):
                if i > 500: term.write("...\n"); break
                term.write(line.rstrip("\r\n") + "\n")
    except OSError as e: term.write("type: %s\n" % e)


