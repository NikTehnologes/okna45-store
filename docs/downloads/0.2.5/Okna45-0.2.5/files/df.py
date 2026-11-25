import os
def run(term, args):
    try:
        st = os.statvfs("/")
        bs = st[0]; total = st[2] * bs; free = st[3] * bs
        term.write("Total: %d KB\n" % (total // 1024))
        term.write("Used:  %d KB\n" % ((total - free) // 1024))
        term.write("Free:  %d KB\n" % (free // 1024))
    except Exception as e: term.write("df: %s\n" % e)


