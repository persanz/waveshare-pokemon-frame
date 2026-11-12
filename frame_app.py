import time
from machine import Pin, SPI, I2C

def start(lcd, power, button):
    import os
    import struct
    import deflate
    import sdcard
    import random

    WHITE = 0xffff
    ORANGE = 0x20fd
    BLACK = 0x0000
    DATA = '/sd/waveshare_pokemon_frame/pokemon_hd.dat'
    MOTION_COOLDOWN = 1500
    MOTION_THRESHOLD = 2200  # gentler shakes for children
    W = 240  # sprite canvas / screen width
    # Landscape is achieved via MADCTL (main.py) so art and text rotate together.
    LANDSCAPE = False


    def message(a, b):
        lcd.fill(0)
        lcd.text(a, max(0, (240-len(a)*8)//2), 100, WHITE)
        lcd.text(b, max(0, (240-len(b)*8)//2), 120, ORANGE)
        lcd.show()


    def draw_goodbye():
        """Procedural goodbye frame: Poké Ball + text."""
        import math
        RED = 0x00f8  # byte-swapped RGB565 red for this display
        Cx = 120
        R = 60
        cy = 110
        lcd.fill(0)
        for y in range(cy - R, cy + R + 1):
            dy = y - cy
            hw = int(math.sqrt(max(0, R*R - dy*dy)))
            if dy < 0:
                lcd.hline(Cx - hw, y, 2*hw, RED)
            else:
                lcd.hline(Cx - hw, y, 2*hw, WHITE)
        lcd.fill_rect(Cx - R, cy - 3, 2*R, 6, 0x0000)
        lcd.ellipse(Cx, cy, 16, 16, 0x0000, True)
        lcd.ellipse(Cx, cy, 10, 10, WHITE, True)
        lcd.ellipse(Cx, cy, 5, 5, 0x0000, True)
        lcd.text('GOODBYE!', (240 - len('GOODBYE!')*8)//2, 200, WHITE)
        lcd.show()


    def read_name(f, name_offset):
        f.seek(name_offset)
        name = b''
        for _ in range(80):
            c = f.read(1)
            if not c or c == b'\0':
                break
            name += c
        try:
            return name.decode('utf-8')
        except Exception:
            return ''


    current_art_id = 0
    current_name = ''
    description_open = False
    description_page = 0
    description_pages = 1

    def show_sprite(index):
        nonlocal current_art_id, current_name, description_open
        description_open = False
        # The order file maps Pokédex order to entries in the artwork archive.
        with open('/pokemon_order.bin', 'rb') as order:
            order.seek(2 + index * 2)
            index = struct.unpack('<H', order.read(2))[0]
        with open(DATA, 'rb') as f:
            f.seek(4 + index * 16)
            number, offset, size, name_offset = struct.unpack('<IIII', f.read(16))
            current_art_id = number
            f.seek(offset)
            stream = deflate.DeflateIO(f, deflate.RAW, 10)
            lcd.fill(0)
            screen = memoryview(lcd.buffer)
            source = bytearray(W * 2)
            for row in range(W):
                if stream.readinto(source) != W * 2:
                    raise OSError('Incomplete sprite')
                start = row * W * 2
                screen[start:start + W * 2] = source
            name = read_name(f, name_offset).upper()
            current_name = name
            # Draw a footer band with the Pokémon number (white) before the name (orange).
            lcd.fill_rect(0, 216, 240, 24, BLACK)
            # Form IDs above 10000 are PokeAPI identifiers, not Pokédex numbers.
            if number >= 10000:
                try:
                    with open('/pokemon_dex.bin', 'rb') as dex:
                        dex.seek((number - 10000) * 2)
                        entry = dex.read(2)
                    number = struct.unpack('<H', entry)[0] if len(entry) == 2 else 0
                except OSError:
                    number = 0
            num_label = str(number) if number else '?'
            max_chars = 30  # 240px / 8px font
            if name:
                total = len(num_label) + 1 + len(name)
                if total <= max_chars:
                    # number before name on one centred line, different colours
                    start_x = (240 - total*8) // 2
                    lcd.text(num_label, start_x, 224, WHITE)
                    lcd.text(name, start_x + len(num_label)*8 + 8, 224, ORANGE)
                else:
                    # long name: number on its own line, name centred below
                    words = name.split(' ')
                    line1 = ''
                    for w in words:
                        if len((line1 + ' ' + w).strip()) <= max_chars:
                            line1 = (line1 + ' ' + w).strip()
                        else:
                            break
                    rest = name[len(line1):].strip()
                    line2 = rest if len(rest) <= max_chars else rest[:max_chars-1] + '…'
                    lcd.text(num_label, (240 - len(num_label)*8)//2, 218, WHITE)
                    lcd.text(line1, (240 - len(line1)*8)//2, 224, ORANGE)
                    if line2:
                        lcd.text(line2, (240 - len(line2)*8)//2, 232, ORANGE)
            else:
                lcd.text(num_label, (240 - len(num_label)*8)//2, 224, WHITE)
            lcd.show()
        print('Displaying Pokemon', number, name)


    try:
        spi = SPI(0, baudrate=1000000, sck=Pin(18), mosi=Pin(19), miso=Pin(20))
        card = sdcard.SDCard(spi, Pin(23, Pin.OUT), baudrate=5000000)
        os.mount(card, '/sd')
        with open(DATA, 'rb') as f:
            count = struct.unpack('<I', f.read(4))[0]
        if not count:
            raise OSError('No images')
        with open('/pokemon_order.bin', 'rb') as order:
            if struct.unpack('<H', order.read(2))[0] != count:
                raise OSError('Artwork order mismatch')
    except Exception as e:
        print('SD setup error:', e)
        message('SD CARD ERROR', 'Reconnect the card')
        while True:
            time.sleep(1)

    imu = None
    for attempt in range(5):
        try:
            imu = I2C(1, sda=Pin(6), scl=Pin(7), freq=50000)
            for reg, val in ((2, 0x60), (3, 0x23), (4, 0x53), (5, 0), (6, 0x11), (7, 0), (8, 3)):
                imu.writeto_mem(0x6b, reg, bytes([val]))
            break
        except OSError as e:
            print('Motion sensor try %d failed:' % (attempt + 1), e)
            time.sleep_ms(200)
    if imu is None:
        print('Motion sensor error')
        message('SENSOR ERROR', 'Restart device')
        return
    print('Motion sensor ready')

    # The touch controller shares I2C1 with the motion sensor.
    touch_ready = False
    try:
        touch_reset = Pin(16, Pin.OUT)
        touch_reset.value(0)
        time.sleep_ms(100)
        touch_reset.value(1)
        time.sleep_ms(100)
        if imu.readfrom_mem(0x15, 0xA7, 1)[0] == 0xB6:
            imu.writeto_mem(0x15, 0xFE, b'\x01')  # disable auto-sleep
            imu.writeto_mem(0x15, 0xFA, b'\x41')  # touch point mode
            touch_ready = True
            print('Touch controller ready')
    except OSError as e:
        print('Touch unavailable:', e)

    # Power-on splash: show the user-provided image with a welcome text.
    try:
        with open('/poweron_art.dat', 'rb') as f:
            screen = memoryview(lcd.buffer)
            f.readinto(screen)
        lcd.fill_rect(0, 216, 240, 24, 0x0000)
        lcd.text('BIENVENIDO A PICODEX', (240 - len('BIENVENIDO A PICODEX')*8)//2, 224, ORANGE)
        lcd.show()
        time.sleep_ms(2000)
    except Exception as e:
        print('Splash skip:', e)

    index = 0  # always start from the first Pokémon on every power-on
    last_motion = time.ticks_add(time.ticks_ms(), -MOTION_COOLDOWN)
    last_sample = time.ticks_ms()
    previous = None
    motion_samples = 0          # consecutive samples above threshold
    motion_armed = True
    still_samples = 0
    MOTION_NEEDED = 2          # two samples (~200ms); reject isolated bumps
    try:
        show_sprite(index)
    except Exception as e:
        print('Image error:', e)
        message('IMAGE ERROR', 'Check SD files')

    # Hardware watchdog: if the main loop ever blocks (e.g. a hung I2C read on
    # battery), the board resets instead of freezing forever.
    try:
        from machine import WDT
        wdt = WDT(timeout=8000)
    except Exception:
        wdt = None

    # Two buttons used: LEFT=GPIO24(previous + power on/off on long), RIGHT=GPIO25
    # (next + first on long). Middle und GPIO16 is unused.
    left_btn = Pin(24, Pin.IN, Pin.PULL_UP)
    right_btn = Pin(25, Pin.IN, Pin.PULL_UP)

    def _debounce(pin, prev):
        v = pin.value()
        if v != prev:
            time.sleep_ms(5)
            v = pin.value()
        return v

    shutdown = False          # standby (screen off) mode
    left_prev = 1
    right_prev = 1
    left_down_since = None
    right_down_since = None
    touch_down = False
    touch_since = 0
    touch_x = 0
    touch_y = 0
    touch_used = False

    while True:
        try:
            if wdt is not None:
                wdt.feed()
            left = _debounce(left_btn, left_prev)
            right = _debounce(right_btn, right_prev)
            now = time.ticks_ms()

            if touch_ready and not shutdown:
                try:
                    point = imu.readfrom_mem(0x15, 0x02, 5)
                    touching = bool(point[0] & 0x0f)
                    if touching:
                        x = ((point[1] & 0x0f) << 8) | point[2]
                        y = ((point[3] & 0x0f) << 8) | point[4]
                        if not touch_down:
                            touch_since = now
                            touch_x, touch_y = x, y
                            touch_used = False
                            if description_open:
                                if description_page+1 < description_pages:
                                    description_page += 1
                                    from dex_description import show as next_page
                                    description_pages = next_page(lcd, current_art_id, current_name, description_page)
                                    import sys
                                    del sys.modules['dex_description']
                                    del next_page
                                else:
                                    show_sprite(index)
                                touch_used = True
                        if not touch_used and 80 <= touch_x < 160 and 40 <= touch_y < 200:
                            if not (80 <= x < 160 and 40 <= y < 200):
                                touch_used = True
                            elif time.ticks_diff(now, touch_since) >= 800:
                                import gc
                                gc.collect()
                                from dex_description import show as show_description
                                description_page = 0
                                description_pages = show_description(lcd, current_art_id, current_name)
                                import sys
                                del sys.modules['dex_description']
                                del show_description
                                gc.collect()
                                description_open = True
                                touch_used = True
                                previous = None
                                motion_samples = 0
                    elif touch_down and not touch_used and not description_open:
                        if 0 <= touch_x < 80 or 160 <= touch_x < 240:
                            index = (index + (-1 if touch_x < 120 else 1)) % count
                            show_sprite(index)
                            previous = None
                            motion_samples = 0
                    touch_down = touching
                except OSError:
                    touch_down = False

            # Left button: short press -> previous; long press -> power off
            if left != left_prev:
                if left == 0:
                    left_down_since = now
                else:
                    if left_down_since is not None:
                        if time.ticks_diff(now, left_down_since) < 1500:
                            if not shutdown:
                                index = (index - 1) % count
                                show_sprite(index)
                                previous = None
                                motion_samples = 0
                    left_down_since = None
                left_prev = left
            else:
                if left == 0 and left_down_since is not None:
                    if time.ticks_diff(now, left_down_since) >= 1500:
                        # Power-off cycle: show goodbye frame, then cut battery power.
                        try:
                            lcd.bl.duty_u16(32768)
                            draw_goodbye()
                        except Exception:
                            pass
                        time.sleep_ms(1500)
                        lcd.bl.duty_u16(0)
                        lcd.fill(0)
                        lcd.show()
                        print('POWER OFF')
                        power.value(0)
                        while True:
                            if wdt is not None:
                                wdt.feed()
                            time.sleep_ms(100)

            # Right button: short press -> next; long press -> first Pokémon
            if right != right_prev:
                if right == 0:
                    right_down_since = now
                else:
                    if right_down_since is not None and not shutdown:
                        if time.ticks_diff(now, right_down_since) < 1500:
                            index = (index + 1) % count
                            show_sprite(index)
                            previous = None
                            motion_samples = 0
                    right_down_since = None
                right_prev = right
            else:
                if right == 0 and right_down_since is not None and not shutdown:
                    if time.ticks_diff(now, right_down_since) >= 2000:
                        index = 0
                        show_sprite(index)
                        previous = None
                        motion_samples = 0
                        right_down_since = None

            # Sustained movement chooses a different random artwork entry.
            # One change per shake; re-arm after half a second of calm.
            if not shutdown and not description_open and not touch_down and left and right and time.ticks_diff(now, last_sample) >= 100:
                last_sample = now
                try:
                    xyz = struct.unpack('<hhh', imu.readfrom_mem(0x6b, 0x35, 6))
                    delta = sum(abs(xyz[i] - previous[i]) for i in range(3)) if previous is not None else 0
                    previous = xyz
                    if not motion_armed:
                        still_samples = still_samples+1 if delta < 1000 else 0
                        if still_samples >= 5:
                            motion_armed = True
                            still_samples = 0
                        motion_samples = 0
                    else:
                        motion_samples = motion_samples + 1 if delta > MOTION_THRESHOLD else 0
                        if count > 1 and motion_samples >= MOTION_NEEDED and time.ticks_diff(now, last_motion) >= MOTION_COOLDOWN:
                            motion_armed = False
                            still_samples = 0
                            candidate = random.randrange(count - 1)
                            if candidate >= index:
                                candidate += 1
                            last_motion = now
                            previous = None
                            motion_samples = 0
                            show_sprite(candidate)
                            index = candidate
                            last_motion = time.ticks_ms()
                            print('PICODEX shuffled')
                except OSError as e:
                    previous = None
                    motion_samples = 0
                    print('PICODEX motion/read error:', e)
            elif shutdown or description_open or touch_down or not left or not right:
                previous = None
                motion_samples = 0

            time.sleep_ms(50)
        except Exception as e:
            # Never let a transient error kill the frame; log and keep going.
            print('loop err:', e)
            previous = None
            motion_samples = 0
            left_prev = left_btn.value()
            right_prev = right_btn.value()
            time.sleep_ms(100)
