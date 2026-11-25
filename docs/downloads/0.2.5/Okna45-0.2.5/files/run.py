"""Run trusted Python in a graphical text window; --gfx is explicit fullscreen."""
def run(term, args):
    if not args:
        term.write('Usage: run [--terminal|--gfx] /file.py [args]\n')
        return
    from ok45_script import file_path, kind, run_file
    selected = None
    if args[0] in ('--terminal', '--gfx'):
        selected, args = args[0][2:], args[1:]
    if not args:
        raise ValueError('Script path is required')
    path = file_path(args[0] if args[0].endswith('.py') else args[0] + '.py')
    selected = selected or kind(path)
    from ok45_desktop import CURRENT
    if CURRENT is not None:
        return CURRENT.launch(path + (' ' + ' '.join(args[1:]) if len(args) > 1 else ''), selected)
    if getattr(term, 'graphical', False) and selected != 'gfx':
        from desktop import run as desktop_run
        return desktop_run(term, [path] + args[1:])
    if selected == 'window':
        return 'desktop ' + path + (' ' + ' '.join(args[1:]) if len(args) > 1 else '')
    if selected == 'gfx':
        term.display_mode = 'gfx'
        term.text.clear()
        term.text.cursor(False)
    try:
        return run_file(path, term, args[1:])
    finally:
        if selected == 'gfx':
            term.text.clear()
            term.text.cursor(True)
            term.display_mode = 'term'


