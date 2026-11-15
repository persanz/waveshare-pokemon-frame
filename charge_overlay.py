"""Load charging UI only while needed, keeping artwork decoder headroom."""
import time

def percentage(mv):
    # Calibrated to this board: the charging plateau measures ~4020 mV (the
    # divider/charger reads ~4 % below the ideal 4.2 V), so that is full charge.
    if not 2500 <= mv <= 4350:
        return None
    points = ((3150, 0), (3450, 10), (3540, 25), (3640, 50),
              (3730, 70), (3920, 90), (4020, 100))
    for i in range(1, len(points)):
        lo, a = points[i-1]
        hi, b = points[i]
        if mv <= hi:
            return max(0, min(100, a + (mv-lo)*(b-a)//(hi-lo)))
    return 100


def level(monitor):
    raw = sum(monitor.adc.read_u16() for _ in range(8)) // 8
    mv = raw * 9900 // 65535
    monitor.mv = mv if monitor.mv is None else (monitor.mv*3+mv)//4
    return percentage(monitor.mv)


def draw(monitor, lcd):
    if not hasattr(monitor, 'adc'):
        from machine import Pin, ADC
        monitor.adc = ADC(Pin(29))
        monitor.mv = None
    value = level(monitor)
    color = 0x00f8 if value is not None and value < 20 else 0x20fd if value is None or value < 70 else 0xe007
    lcd.fill(0)
    lcd.ellipse(120, 112, 85, 85, color, True)
    lcd.ellipse(120, 112, 77, 77, 0, True)
    # Scale the built-in glyphs using just a 40-byte temporary framebuffer.
    import framebuf
    label = '--%' if value is None else str(value)+'%'
    buf = bytearray(len(label)*8)
    glyph = framebuf.FrameBuffer(buf, len(label)*8, 8, framebuf.MONO_HLSB)
    glyph.text(label, 0, 0, 1)
    x0 = (240-len(label)*32)//2
    for y in range(8):
        for x in range(len(label)*8):
            if glyph.pixel(x, y):
                lcd.fill_rect(x0+x*4, 96+y*4, 4, 4, 0xffff)
    lcd.text('CARGANDO', 88, 150, 0xffff)
    if value is None:
        label = 'BATERIA NO VERIFICADA'
        lcd.text(label, (240-len(label)*8)//2, 205, 0xffff)
    lcd.text('TOCA PARA VOLVER', 60, 224, 0xffff)
    lcd.show()


def run(monitor, lcd, bus, left, power, wdt=None, save=None):
    # Stream the existing framebuffer to flash, never allocate a second one.
    path = '/charge-screen.tmp'
    with open(path, 'wb') as f:
        f.write(lcd.buffer)
    try:
        draw(monitor, lcd)
        print('Power screen displayed')
        released = False
        dismiss_requested = False
        high_since = held = None
        refresh = time.ticks_ms()
        while True:
            if wdt:
                wdt.feed()
            now = time.ticks_ms()
            if not left.value():
                if held is None:
                    held = now
                elif time.ticks_diff(now, held) >= 1500:
                    if save:
                        save()
                    from shutdown_screen import show
                    show(lcd)
                    power.value(0)
                    while True:
                        if wdt:
                            wdt.feed()
                        time.sleep_ms(100)
            else:
                held = None
            down = False
            if bus is not None:
                try:
                    down = bool(bus.readfrom_mem(0x15, 2, 1)[0] & 15)
                except OSError:
                    pass
            if not down:
                released = True
            if down and released:
                dismiss_requested = True
            # Keep checking power while waiting for the dismissal finger to lift.
            if dismiss_requested and not down:
                break
            if not monitor.pin.value():
                if high_since is None:
                    high_since = now
                elif time.ticks_diff(now, high_since) >= 700:
                    break
            else:
                high_since = None
            if time.ticks_diff(now, refresh) >= 1000:
                draw(monitor, lcd)
                refresh = now
            time.sleep_ms(30)
    finally:
        with open(path, 'rb') as f:
            f.readinto(lcd.buffer)
        lcd.show()
        import os
        os.remove(path)
    return True
