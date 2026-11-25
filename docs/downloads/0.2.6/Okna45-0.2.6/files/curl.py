"""HTTP GET. Usage: curl <url>"""
import urequests

def run(term, args):
    if not args:
        term.write("Usage: curl <url>\n")
        return
    try:
        r = urequests.get(args[0])
        term.write(f"HTTP {r.status_code}\n")
        text = r.text
        r.close()
        for line in text.split('\n')[:15]:
            term.write(line[:40] + '\n')
    except Exception as e:
        term.write(f"Error: {e}\n")

