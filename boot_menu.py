"""Touch launcher. Returns before loading an app to keep the heap small."""
import time
from machine import Pin, I2C


def draw(lcd):
    # Driver stores RGB565 bytes in display order.
    def rgb(r, g, b):
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        return ((v & 255) << 8) | (v >> 8)
    bg = rgb(12, 18, 32)
    panel = rgb(25, 36, 56)
    white = 0xffff
    gold = rgb(255, 204, 65)
    blue = rgb(86, 196, 255)
    red = rgb(245, 72, 88)
    ink = rgb(25, 27, 36)
    lcd.fill(bg)
    # Pokeball header emblem.
    lcd.ellipse(26, 21, 13, 13, white, True)
    for y in range(9, 21):
        dy = y - 21
        half = int((169 - dy*dy) ** 0.5)
        lcd.hline(26-half, y, half*2+1, red)
    lcd.hline(13, 21, 27, ink)
    lcd.ellipse(26, 21, 4, 4, ink, True)
    lcd.ellipse(26, 21, 2, 2, white, True)
    lcd.text('POKEMON', 55, 13, white)
    lcd.text('ELIGE TU MUNDO', 55, 26, blue)
    for x, accent in ((8, gold), (124, blue)):
        lcd.fill_rect(x, 49, 108, 166, panel)
        lcd.rect(x, 49, 108, 166, accent)
        lcd.fill_rect(x+1, 50, 106, 3, accent)
    # Cached RGB565 thumbnails of the real artwork; stream one row at a time.
    screen = memoryview(lcd.buffer)
    row = bytearray(192)
    for x, path in ((14, '/menu_pikachu.dat'), (130, '/menu_pokedex.dat')):
        try:
            with open(path, 'rb') as f:
                for y in range(96):
                    if f.readinto(row) != 192:
                        raise OSError('Incomplete menu image')
                    pos = ((66+y)*240+x)*2
                    screen[pos:pos+192] = row
        except OSError as e:
            print('Menu image error:', path, e)
            lcd.text('?', x+44, 110, white)
    lcd.text('Virtual', 34, 171, gold)
    lcd.text('Pokemon', 34, 185, white)
    lcd.text('PICODEX', 150, 178, blue)
    # Hardware-button hints are represented by left/right chevrons.
    lcd.line(61, 203, 57, 207, gold)
    lcd.line(57, 207, 61, 211, gold)
    lcd.line(178, 203, 182, 207, blue)
    lcd.line(182, 207, 178, 211, blue)
    # Small power icon reminds of long-left power off.
    lcd.ellipse(120, 228, 6, 6, blue)
    lcd.fill_rect(118, 220, 5, 6, bg)
    lcd.vline(120, 219, 8, white)
    lcd.show()


def choose(lcd, power, left):
    draw(lcd)
    print('Boot menu ready: Virtual Pokemon / PICODEX')
    right = Pin(25, Pin.IN, Pin.PULL_UP)
    bus = None
    try:
        bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=50000)
        reset = Pin(16, Pin.OUT, value=0)
        time.sleep_ms(100)
        reset.value(1)
        time.sleep_ms(100)
        if bus.readfrom_mem(0x15, 0xA7, 1)[0] != 0xB6:
            bus = None
        else:
            bus.writeto_mem(0x15, 0xFE, b'\x01')
            bus.writeto_mem(0x15, 0xFA, b'\x41')
    except OSError as e:
        print('Menu touch unavailable; use buttons:', e)
        bus = None
    # Ignore the power-on press and wait for a fresh input.
    armed = False
    left_since = None
    while True:
        now = time.ticks_ms()
        down = False
        point = None
        if bus is not None:
            try:
                point = bus.readfrom_mem(0x15, 0x02, 5)
                down = bool(point[0] & 15)
            except OSError:
                point = None
        lv, rv = left.value(), right.value()
        if not armed:
            armed = bool(lv and rv and not down)
        else:
            if down and point:
                x = ((point[1]&15)<<8) | point[2]
                y = ((point[3]&15)<<8) | point[4]
                if 49 <= y < 215:
                    if 8 <= x < 116:
                        return 'companion_app'
                    if 124 <= x < 232:
                        return 'frame_app'
            if not lv:
                if left_since is None:
                    left_since = now
                elif time.ticks_diff(now, left_since) >= 1500:
                    from shutdown_screen import show as goodbye
                    goodbye(lcd)
                    power.value(0)
                    while True:
                        time.sleep_ms(100)
            elif left_since is not None:
                return 'companion_app'
            if not rv:
                return 'frame_app'
        time.sleep_ms(30)
