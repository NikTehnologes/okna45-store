import os
def run(term, args):
    try: term.write(os.getcwd() + "\n")
    except: term.write("(cwd not supported)\n")


