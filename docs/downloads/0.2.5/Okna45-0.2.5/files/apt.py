"""Small apt-like manager. Start with apt update; then apt install hello."""


def run(term, args):
    from ok45_pkg import PackageManager
    for message in PackageManager().command_job(args):
        if message:
            term.write(message + '\n')
