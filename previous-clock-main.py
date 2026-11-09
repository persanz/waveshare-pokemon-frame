# Clock — Waveshare RP2350-Touch-LCD-1.54 (MicroPython)
#
# Just the time. The Pico has no RTC/WiFi, so the Mac sends the date/time over USB serial:
#     S|DT:YYYY-MM-DD:HH:MM:SS:WD|TS:HH:MM:SS
import gc
import select
import sys
import time

import framebuf
from machine import RTC, ADC, Pin
# Hold the battery power circuit on as soon as the app starts.
battery_enable = Pin(28, Pin.OUT, value=1)
power_button = Pin(24, Pin.IN, Pin.PULL_UP)

from lcd import LCD_1inch54

WHITE = 0xFFFF
BG    = 0x0841
DIM   = 0x4A69
CYAN  = 0x07FF
ORANGE = 0x20FD        # byte-swapped RGB565 orange for this LCD
BLUE  = 0x249F          # bright blue for the weekday

DOW = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

TIME_FILE = "clock.dat"        # last known time, so the clock survives a power cycle


def save_time():
    t = time.localtime()
    try:
        with open(TIME_FILE, "w") as f:
            f.write("%d,%d,%d,%d,%d,%d,%d" % (t[0], t[1], t[2], t[3], t[4], t[5], t[6]))
    except Exception:
        pass


def load_time():
    """Restore the RTC from flash at boot. Returns True if a saved time was found."""
    try:
        with open(TIME_FILE) as f:
            p = f.read().strip().split(",")
        rtc.datetime((int(p[0]), int(p[1]), int(p[2]), int(p[6]),
                      int(p[3]), int(p[4]), int(p[5]), 0))
        return True
    except Exception:
        return False


gc.collect()
lcd = LCD_1inch54()
# Fixed orientation calibrated to the clock position.
lcd.write_cmd(0x36)
lcd.write_data(0x60)
import charging
import battery_log
rtc = RTC()
battery_adc = ADC(Pin(29))
time_set = load_time()   # resume from the last saved time if we have one

poll = select.poll()
serial_input = sys.stdin.buffer
poll.register(serial_input, select.POLLIN)

_glyph = bytearray(8 * 8 * 2)
_gfb = framebuf.FrameBuffer(_glyph, 8, 8, framebuf.RGB565)


def text(s, x, y, scale, color):
    for i, ch in enumerate(s):
        _gfb.fill(BG)
        _gfb.text(ch, 0, 0, color)
        cx = x + i * 8 * scale
        for yy in range(8):
            for xx in range(8):
                if _gfb.pixel(xx, yy) != BG:
                    lcd.fill_rect(cx + xx * scale, y + yy * scale, scale, scale, color)


def ctext(s, y, scale, color):
    text(s, max(0, (240 - len(s) * 8 * scale) // 2), y, scale, color)


def draw_battery():
    # Waveshare demo uses a 3:1 divider on GPIO 29. Percentage is only
    # an approximate resting-voltage indication for a single Li-ion cell.
    voltage = sum(battery_adc.read_u16() for _ in range(8)) * 3.3 * 3 / (8 * 65535)
    if voltage < 3.0 or voltage > 4.3:
        label = "%.1fV?" % voltage
    else:
        percent = max(0, min(100, int((voltage - 3.0) * 100 / 1.2)))
        label = "%d%%" % percent
    line = "Battery " + label
    x = (240 - len(line) * 8 - 10) // 2
    text(line, x, 211, 1, ORANGE)
    charging.draw(lcd, ORANGE, x + len(line) * 8 + 2, 211)


def draw_clock():
    lcd.fill(BG)
    if not time_set:
        ctext("CLOCK", 40, 3, CYAN)
        ctext("syncing...", 120, 2, DIM)
    else:
        t = time.localtime()
        ctext("%02d:%02d:%02d" % (t[3], t[4], t[5]), 47, 3, WHITE)
        ctext("%02d %s %d" % (t[2], MON[t[1] - 1], t[0]), 128, 2, CYAN)
        ctext(DOW[t[6]], 162, 2, BLUE)
    draw_battery()
    lcd.show()


def handle(line):
    global time_set
    line = line.strip()
    if not (line.startswith("S|") or line.startswith("F|")):
        return False
    for part in line.split("|")[1:]:
        f = part.split(":")
        if f[0] == "DT":
            try:
                y, mo, d = f[1].split("-")
                rtc.datetime((int(y), int(mo), int(d), int(f[5]),
                              int(f[2]), int(f[3]), int(f[4]), 0))
                time_set = True
                save_time()
            except Exception:
                pass
    return True


gc.collect()
draw_clock()
_tick = time.ticks_ms()
_saved_min = time.localtime()[4]
# Ignore the button used to start the board until it has been released.
_power_armed = False
_power_pressed_at = None
_power_shutdown = False
_serial_buffer = ""
while True:
    pressed = power_button.value() == 0
    if not _power_armed:
        if not pressed:
            _power_armed = True
    elif pressed:
        if _power_pressed_at is None:
            _power_pressed_at = time.ticks_ms()
        elif not _power_shutdown and time.ticks_diff(time.ticks_ms(), _power_pressed_at) >= 2000:
            _power_shutdown = True
            if time_set:
                save_time()
            lcd.fill(BG)
            ctext("Release", 90, 2, CYAN)
            ctext("to power off", 125, 2, CYAN)
            lcd.show()
    else:
        if _power_shutdown:
            lcd.fill(0)
            lcd.show()
            battery_enable.value(0)
            while True:
                time.sleep_ms(100)
        _power_pressed_at = None
    if _power_shutdown:
        time.sleep_ms(50)
        continue
    if poll.poll(0):
        try:
            ch = serial_input.read(1)
        except Exception:
            ch = ""
        if ch in (b"\n", b"\r"):
            if _serial_buffer and handle(_serial_buffer):
                print("K")
                draw_clock()
            _serial_buffer = ""
        elif ch:
            _serial_buffer = (_serial_buffer + chr(ch[0]))[-128:]
    now = time.ticks_ms()
    if time.ticks_diff(now, _tick) >= 1000:
        _tick = now
        draw_clock()
        battery_log.update(battery_adc, charging.is_charging())
        if time_set and time.localtime()[4] != _saved_min:   # once a minute: persist the time
            _saved_min = time.localtime()[4]
            save_time()
    time.sleep_ms(50)
