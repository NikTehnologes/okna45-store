from machine import Pin
_led = Pin('LED', Pin.OUT)
def run(term, args):
    if not args: term.write("LED: %s\n" % ('on' if _led.value() else 'off'))
    elif args[0] == 'on': _led.value(1); term.write("LED on\n")
    elif args[0] == 'off': _led.value(0); term.write("LED off\n")
    else: term.write("Usage: led [on|off]\n")


