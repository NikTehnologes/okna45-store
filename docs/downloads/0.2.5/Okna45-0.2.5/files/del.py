import os
def run(term, args):
    if not args: term.write("Usage: del <file>\n"); return
    try:
        os.remove(args[0]); term.write("Deleted\n")
    except OSError as e: term.write("del: %s\n" % e)


