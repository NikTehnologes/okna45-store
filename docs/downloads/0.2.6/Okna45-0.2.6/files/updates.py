"""Remote OS updates. App packages still use apt; apply exits GUI and reboots."""
def run(term, args):
    from ok45_store import StoreService
    service = StoreService()
    applying = bool(args and args[0] == 'apply' and service.pending())
    for message in service.command_job(args):
        if message:
            term.write(message + '\n')
    if applying:
        term.write('Restarting Okna45...\n')
        import machine
        machine.reset()
