"""Install trusted desktop software: install /path/app.sin."""
def run(term, args):
    if len(args) != 1:
        term.write('Usage: install /path/app.sin\n')
        return
    from ok45_pkg import PackageManager
    for message in PackageManager().bundle_job(args[0]):
        if message:
            term.write(message + '\n')
