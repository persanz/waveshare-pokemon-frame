"""Pico virtual pet: touch care, movement encounters, existing RGB565 archive."""
import time
from machine import Pin, SPI, I2C


def start(lcd, power, button):
    import gc
    gc.collect()
    import os
    import struct
    import deflate
    import random
    import json
    import sdcard
    from companion_state import Pet
    # Display driver uses byte-swapped RGB565 values.
    WHITE, ORANGE, BLACK, GREEN = 0xffff, 0x20fd, 0, 0xe007
    DATA = '/sd/waveshare_pokemon_frame/pokemon_hd.dat'
    MOTION_THRESHOLD = 2200  # gentler shakes for children
    MOTION_NEEDED = 2
    MOTION_COOLDOWN = 1500
    STATE = '/companion.json'
    pet = Pet()
    title = 'POKEMON'
    notice = ''
    notice_until = 0

    def center(text, y, color=WHITE):
        text = text[:29]
        lcd.text(text, (240-len(text)*8)//2, y, color)

    def status():
        lcd.fill_rect(0, 0, 240, 24, BLACK)
        lcd.text('COMIDA', 4, 3, ORANGE)
        lcd.text('ANIMO', 126, 3, GREEN)
        for x, value, color in ((4, pet.food, ORANGE), (126, pet.joy, GREEN)):
            lcd.rect(x, 14, 106, 7, WHITE)
            lcd.fill_rect(x+1, 15, value*104//100, 5, color)
        lcd.fill_rect(0, 176, 240, 64, BLACK)
        center(title, 178, ORANGE)
        center(notice if time.ticks_diff(notice_until, time.ticks_ms()) > 0 else pet.mood(), 193)
        for x, label in ((0, 'COMIDA'), (80, 'CARICIA'), (160, 'JUGAR')):
            lcd.rect(x+2, 209, 76, 28, ORANGE)
            lcd.text(label, x+(80-len(label)*8)//2, 219, WHITE)
        lcd.show()

    def say(text):
        nonlocal notice, notice_until
        notice, notice_until = text, time.ticks_add(time.ticks_ms(), 1800)
        status()

    def save():
        try:
            with open(STATE+'.tmp', 'w') as f:
                json.dump({'index': pet.index, 'food': pet.food, 'joy': pet.joy}, f)
            os.rename(STATE+'.tmp', STATE)
        except Exception as e:
            print('Pet save error:', e)

    def show():
        nonlocal title
        gc.collect()
        with open('/pokemon_order.bin', 'rb') as order:
            order.seek(2 + pet.index*2)
            raw = order.read(2)
            if len(raw) != 2:
                raise OSError('Missing order entry')
            entry = struct.unpack('<H', raw)[0]
        with open(DATA, 'rb') as f:
            f.seek(4 + entry*16)
            number, offset, size, name_offset = struct.unpack('<IIII', f.read(16))
            f.seek(offset)
            stream = deflate.DeflateIO(f, deflate.RAW, 10)
            lcd.fill(BLACK)
            screen = memoryview(lcd.buffer)
            source = bytearray(480)
            row_out = bytearray(304)
            target = 0
            # Fit the complete 240px image into a 152px square; no artwork crop.
            for row in range(240):
                if row % 24 == 0:
                    gc.collect()
                if stream.readinto(source) != 480:
                    raise OSError('Incomplete artwork')
                if target < 152 and row == target*240//152:
                    for x in range(152):
                        src = (x*240//152)*2
                        row_out[x*2] = source[src]
                        row_out[x*2+1] = source[src+1]
                    pos = ((24+target)*240+44)*2
                    screen[pos:pos+304] = row_out
                    target += 1
            f.seek(name_offset)
            name = bytearray()
            for _ in range(80):
                c = f.read(1)
                if not c or c == b'\0':
                    break
                name.extend(c)
            name = name.decode('utf-8', 'replace').upper()
            if number >= 10000:
                with open('/pokemon_dex.bin', 'rb') as dex:
                    dex.seek((number-10000)*2)
                    raw = dex.read(2)
                number = struct.unpack('<H', raw)[0] if len(raw) == 2 else 0
            # Built-in display font is ASCII; keep unsupported symbols readable.
            title = ('#%s %s' % (number or '?', name)).encode('ascii', 'replace').decode()
        status()
        print('Companion displayed:', title, 'food', pet.food, 'joy', pet.joy)

    def error(text):
        lcd.fill(BLACK)
        center(text, 100, ORANGE)
        center('MANTEN IZQ. PARA APAGAR', 120)
        lcd.show()

    try:
        spi = SPI(0, baudrate=1000000, sck=Pin(18), mosi=Pin(19), miso=Pin(20))
        card = sdcard.SDCard(spi, Pin(23, Pin.OUT), baudrate=5000000)
        os.mount(card, '/sd')
        with open(DATA, 'rb') as f:
            count = struct.unpack('<I', f.read(4))[0]
        with open('/pokemon_order.bin', 'rb') as f:
            if not count or struct.unpack('<H', f.read(2))[0] != count:
                raise OSError('Artwork order mismatch')
    except Exception as e:
        print('SD error:', e)
        error('REVISA LOS ARCHIVOS SD')
        # Keep the power button functional even if setup fails.
        while True:
            if not button.value():
                time.sleep_ms(1500)
                if not button.value():
                    gc.collect()
                    from shutdown_screen import show as goodbye
                    goodbye(lcd)
                    power.value(0)
            time.sleep_ms(50)

    try:
        with open(STATE) as f:
            saved = json.load(f)
        pet = Pet(saved.get('index', 0), saved.get('food', 75), saved.get('joy', 75))
    except (OSError, ValueError, TypeError):
        pass
    pet.index %= count
    # Touch and IMU share a bus, but either may work without the other.
    bus = I2C(1, sda=Pin(6), scl=Pin(7), freq=50000)
    motion_ready = False
    try:
        if bus.readfrom_mem(0x6b, 0, 1)[0] != 5:
            raise OSError('Unexpected IMU identity')
        for reg, value in ((2, 0x60), (3, 0x23), (4, 0x53), (5, 0), (6, 0x11), (7, 0), (8, 3)):
            bus.writeto_mem(0x6b, reg, bytes([value]))
        motion_ready = True
    except OSError as e:
        print('Motion unavailable; touch/buttons remain active:', e)
    touch_ready = False
    try:
        reset = Pin(16, Pin.OUT, value=0)
        time.sleep_ms(100)
        reset.value(1)
        time.sleep_ms(100)
        if bus.readfrom_mem(0x15, 0xA7, 1)[0] == 0xB6:
            bus.writeto_mem(0x15, 0xFE, b'\x01')
            bus.writeto_mem(0x15, 0xFA, b'\x41')
            touch_ready = True
    except OSError as e:
        print('Touch unavailable:', e)
    print('Companion inputs: touch', touch_ready, 'motion', motion_ready)
    try:
        from machine import WDT
        wdt = WDT(timeout=8000)
    except Exception:
        wdt = None
    right = Pin(25, Pin.IN, Pin.PULL_UP)
    touched, right_was = False, 1
    left_since = None
    previous = None
    movement = 0
    motion_armed = True
    still_samples = 0
    last_tick = last_save = last_sample = last_ui = time.ticks_ms()
    last_encounter = time.ticks_add(last_tick, -MOTION_COOLDOWN)

    def encounter():
        nonlocal previous, movement, last_encounter
        new_index = random.randrange(count-1) if count > 1 else 0
        if count > 1 and new_index >= pet.index:
            new_index += 1
        old = (pet.index, pet.food, pet.joy)
        pet.encounter(new_index)
        try:
            show()
            say('UN NUEVO AMIGO!')
            save()
        except Exception as e:
            pet.index, pet.food, pet.joy = old
            print('Encounter artwork error:', e)
            say('ERROR DE IMAGEN - REVISA SD')
        previous, movement = None, 0
        last_encounter = time.ticks_ms()

    try:
        show()
    except Exception as e:
        import sys
        sys.print_exception(e)
        print('Artwork error:', e)
        error('ERROR DE IMAGEN - REVISA SD')

    while True:
        if wdt:
            wdt.feed()
        now = time.ticks_ms()
        # Power handling always runs before input and SD work.
        if not button.value():
            if left_since is None:
                left_since = now
            elif time.ticks_diff(now, left_since) >= 1500:
                save()
                gc.collect()
                from shutdown_screen import show as goodbye
                goodbye(lcd)
                power.value(0)
                while True:
                    if wdt:
                        wdt.feed()
                    time.sleep_ms(100)
        else:
            if left_since is not None and time.ticks_diff(now, left_since) < 1500:
                say(pet.action('feed'))
            left_since = None
        try:
            seconds = time.ticks_diff(now, last_tick)//1000
            if seconds:
                pet.advance(seconds)
                last_tick = time.ticks_add(last_tick, seconds*1000)
            if touch_ready:
                try:
                    point = bus.readfrom_mem(0x15, 0x02, 5)
                    down = bool(point[0] & 15)
                    if down and not touched:
                        x = ((point[1]&15)<<8) | point[2]
                        y = ((point[3]&15)<<8) | point[4]
                        if 0 <= x < 240 and 0 <= y < 240:
                            kind = ('feed' if x < 80 else 'pet' if x < 160 else 'play') if y >= 208 else 'pet'
                            say(pet.action(kind))
                    touched = down
                except OSError:
                    touched = False
            value = right.value()
            if right_was and not value:
                say(pet.action('play'))
            right_was = value
            if motion_ready and time.ticks_diff(now, last_sample) >= 100:
                last_sample = now
                try:
                    xyz = struct.unpack('<hhh', bus.readfrom_mem(0x6b, 0x35, 6))
                    delta = sum(abs(xyz[i]-previous[i]) for i in range(3)) if previous else 0
                    previous = xyz
                    if not motion_armed:
                        still_samples = still_samples+1 if delta < 1000 else 0
                        if still_samples >= 5:
                            motion_armed = True
                            still_samples = 0
                        movement = 0
                    else:
                        movement = movement+1 if delta > MOTION_THRESHOLD else 0
                        if movement >= MOTION_NEEDED and time.ticks_diff(now, last_encounter) >= MOTION_COOLDOWN:
                            motion_armed = False
                            still_samples = 0
                            encounter()
                except OSError:
                    previous, movement = None, 0
            if time.ticks_diff(now, last_ui) >= 1000:
                status()
                last_ui = now
            if time.ticks_diff(now, last_save) >= 300000:
                save()
                last_save = now
        except Exception as e:
            print('Companion loop error:', e)
        time.sleep_ms(50)
