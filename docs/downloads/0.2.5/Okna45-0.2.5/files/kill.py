"""Cancel a cooperative user task; system services are protected."""


def run(term, args):
    import ok45_kernel
    scheduler = ok45_kernel.CURRENT
    if scheduler is None or not args:
        term.write('Usage: kill ID (inside desktop console)\n')
        return
    identity = int(args[0])
    task = scheduler.find(identity)
    if task is None or task.owner is None:
        term.write('Task missing or protected\n')
    else:
        scheduler.cancel(identity)
        term.write('Cancelled %d\n' % identity)
