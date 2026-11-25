import gc, sys
def run(term, args):
    term.write("MicroPython %s\n" % sys.version.split()[0])
    term.write("Free RAM: %d B\n" % gc.mem_free())
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        if wlan.active() and wlan.isconnected():
            term.write("WiFi: %s\n" % wlan.ifconfig()[0])
        else: term.write("WiFi: offline\n")
    except: pass


