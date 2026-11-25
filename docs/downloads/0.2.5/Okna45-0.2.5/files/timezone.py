"""Persistent timezone: timezone [UTC|Europe/Moscow|+05:00|-03:30]."""
def run(term, args):
    import ok45_time as clock
    value = clock.set_timezone(args[0]) if args else clock.settings()
    term.write('%s (%s); RTC UTC; automatic DST off\n' %
               (value['label'], clock.offset_text(value['offset_minutes'])))
