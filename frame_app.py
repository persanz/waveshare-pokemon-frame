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
    MOTION_COOLDOWN = 3000
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
        RED = 0xf800
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


    def show_sprite(index):
        with open(DATA, 'rb') as f:
            f.seek(4 + index * 16)
            number, offset, size, name_offset = struct.unpack('<IIII', f.read(16))
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
            # Draw a footer band with the Pokémon number (white) before the name (orange).
            lcd.fill_rect(0, 216, 240, 24, BLACK)
            num_label = str(number)
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

    # Power-on splash: show the user-provided image with a welcome text.
    try:
        with open('/poweron_art.dat', 'rb') as f:
            screen = memoryview(lcd.buffer)
            f.readinto(screen)
        lcd.fill_rect(0, 216, 240, 24, 0x0000)
        lcd.text('WELCOME TO PICODEX', (240 - len('WELCOME TO PICODEX')*8)//2, 224, ORANGE)
        lcd.show()
        time.sleep_ms(2000)
    except Exception as e:
        print('Splash skip:', e)

    index = 0  # always start from the first Pokémon on every power-on
    last_motion = time.ticks_ms()
    last_sample = time.ticks_ms()
    previous = None
    motion_samples = 0          # consecutive samples above threshold
    MOTION_NEEDED = 3          # require ~3 sustained samples (~300ms) of motion
    try:
        show_sprite(index)
    except Exception as e:
        print('Image error:', e)
        message('IMAGE ERROR', 'Check SD files')

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
    while True:
        left = _debounce(left_btn, left_prev)
        right = _debounce(right_btn, right_prev)
        now = time.ticks_ms()

        # Left button: short press -> previous; long press -> power on/off
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
                    # Power-off cycle: show procedural goodbye frame, then cut battery power.
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
                        time.sleep_ms(100)
                    left_down_since = None  # (unreachable) consume

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

        if not shutdown and time.ticks_diff(now, last_sample) >= 100:
            last_sample = now
            try:
                raw = imu.readfrom_mem(0x6b, 0x35, 12)
                values = [raw[i] | (raw[i + 1] << 8) for i in range(0, 12, 2)]
                values = [v - 65536 if v >= 32768 else v for v in values]
                if previous is not None:
                    acceleration = max(abs(values[i] - previous[i]) for i in range(3))
                    rotation = max(abs(values[i]) for i in range(3, 6))
                    if (acceleration > 2200 or rotation > 5000):
                        motion_samples += 1
                    else:
                        motion_samples = 0
                    if (motion_samples >= MOTION_NEEDED
                            and time.ticks_diff(now, last_motion) >= MOTION_COOLDOWN):
                        last_motion = now
                        motion_samples = 0
                        index = random.randrange(count)  # random Pokémon on movement
                        show_sprite(index)
                        previous = None
                        continue
                previous = values
            except OSError:
                previous = None
                motion_samples = 0
        time.sleep_ms(50)
        # diagnostic: catch any loop crash so the board doesn't hang silently
        # (wrapped in next iterations by the outer try below)
