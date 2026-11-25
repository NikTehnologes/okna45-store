"""Okna45 0.2.4: graphical boot, one compositor, no resident PicoTerm grid."""
import gc
import sys
from machine import Pin, SPI, I2C, PWM
from ili9341 import Display

spi0 = SPI(0, baudrate=40_000_000, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
_d = Display(spi0, cs=Pin(17), dc=Pin(21), rst=Pin(20),
             width=320, height=240, rotation=0, bgr=False)
backlight = PWM(Pin(14)); backlight.freq(1000); backlight.duty_u16(32768)
i2c = I2C(1, sda=Pin(2, Pin.PULL_UP), scl=Pin(3, Pin.PULL_UP), freq=100_000)
CARDKB = 0x5F


class Device:
    def __init__(self, display):
        self.d = display
        self.row = 0
        self.graphical = True

    def readkey(self):
        try:
            data = i2c.readfrom(CARDKB, 1)
            return data[0] if data else 0
        except OSError:
            return 0

    def write(self, value):
        # Maintenance progress while the desktop is safely unloaded. No grid.
        print(value, end='')
        for line in str(value).split('\n'):
            if not line:
                continue
            self.d.fill_rectangle(0, self.row * 10, 320, 10, 0)
            self.d.draw_text8x8(4, self.row * 10, line[:39], 65535, 0)
            self.row = (self.row + 1) % 24


term = Device(_d)


def execute(device, value):
    """Compatibility API for tools; normal commands remain in graphical windows."""
    from ok45_desktop import CURRENT
    if CURRENT is not None:
        return CURRENT.launch(value)
    return value


def maintenance(value):
    parts = value.split()
    if not parts:
        return
    before = set(sys.modules)
    module = None
    try:
        term.row = 0
        _d.clear(hlines=1)
        if parts[0] in ('updates', 'update'):
            module = __import__(parts[0])
            module.run(term, parts[1:])
        elif parts[0] == 'reboot':
            import machine
            machine.reset()
        else:
            from ok45_legacy import fullscreen
            fullscreen(term, value)
    except Exception as error:
        printer = getattr(sys, 'print_exception', None)
        if printer:
            printer(error)
        term.write('Error: %s: %s\n' % (type(error).__name__, error))
        import time
        while term.readkey() not in (10, 13, 27):
            time.sleep_ms(20)
    finally:
        module = None
        fullscreen = None
        for name in tuple(sys.modules):
            if name not in before and (name.startswith('ok45_') or
                    name in ('run', 'updates', 'update', 'urequests', 'requests')):
                del sys.modules[name]
        gc.collect()


print('Okna45 0.2.4 / graphical boot')
while True:
    from desktop import run
    launch = run(term, [])
    run = None
    if 'desktop' in sys.modules:
        del sys.modules['desktop']
    gc.collect()
    if launch:
        maintenance(launch)
        launch = None
