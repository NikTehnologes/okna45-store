"""Graphical desktop lifecycle; fullscreen compatibility is demand-loaded."""
MODE = 'gfx'


def run(term, args):
    import gc
    import sys
    before = set(sys.modules)
    threshold = getattr(gc, 'threshold', None)
    previous = threshold() if threshold else None
    desktop = Desktop = None
    gc.collect()
    try:
        if threshold:
            threshold(gc.mem_alloc() + gc.mem_free() // 4)
        from ok45_desktop import Desktop
        desktop = Desktop(term)
        desktop.run(initial=' '.join(args) if args else None)
        # Release the compositor and app code before any maintenance/fullscreen.
        return desktop.shell_launch
    finally:
        if desktop is not None:
            desktop.shutdown()
        desktop = Desktop = None
        for name in tuple(sys.modules):
            if name not in before and (name.startswith('ok45_') or
                                       name in ('urequests', 'requests', 'ntptime')):
                del sys.modules[name]
        if threshold:
            threshold(previous)
        gc.collect()
