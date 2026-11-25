import os
def run(term, args):
    if len(args) < 2: term.write("Usage: ren <src> <dst>\n"); return
    try:
        os.rename(args[0], args[1]); term.write("Renamed\n")
    except OSError as e: term.write("ren: %s\n" % e)


