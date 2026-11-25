"""Apply a trusted .sin system/software update without replacing the whole flash."""
def run(term, args):
    from ok45_update import Updater
    for message in Updater().command_job(args):
        if message:
            term.write(message + '\n')
