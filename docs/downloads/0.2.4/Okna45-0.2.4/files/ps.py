"""Show cooperative desktop tasks. Desktop task view: Start -> Task manager."""


def run(term, args):
    import ok45_kernel
    scheduler = ok45_kernel.CURRENT
    if scheduler is None:
        term.write('No desktop scheduler; run desktop\n')
        return
    for task in scheduler.snapshot()['tasks']:
        term.write('%d %-16s %-8s %d\n' % (task['id'], task['name'], task['state'], task['runs']))
