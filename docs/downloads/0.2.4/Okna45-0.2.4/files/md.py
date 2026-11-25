import os
def run(term, args):
    if not args: term.write("Usage: md <name>\n"); return
    try:
        os.mkdir(args[0]); term.write("Created\n")
    except OSError as e: term.write("md: %s\n" % e)


