"""The original frame's Pokeball goodbye screen, shared by the launcher and pet."""
import gc
import time
WHITE = 0xffff

def draw(lcd):
    """Procedural goodbye frame: Poké Ball + text."""
    import math
    RED = 0x00f8  # byte-swapped RGB565 red for this display
    Cx = 120
    R = 60
    cy = 110
    lcd.fill(0)
    for y in range(cy - R, cy + R + 1):
        dy = y - cy
        hw = int(math.sqrt(max(0, R * R - dy * dy)))
        if dy < 0:
            lcd.hline(Cx - hw, y, 2 * hw, RED)
        else:
            lcd.hline(Cx - hw, y, 2 * hw, WHITE)
    lcd.fill_rect(Cx - R, cy - 3, 2 * R, 6, 0)
    lcd.ellipse(Cx, cy, 16, 16, 0, True)
    lcd.ellipse(Cx, cy, 10, 10, WHITE, True)
    lcd.ellipse(Cx, cy, 5, 5, 0, True)
    lcd.text('ADIOS!', (240 - len('ADIOS!') * 8) // 2, 200, WHITE)
    lcd.show()


def show(lcd):
    gc.collect()
    try:
        lcd.bl.duty_u16(32768)
        draw(lcd)
    except Exception as e:
        print('Shutdown screen error:', e)
    time.sleep_ms(1500)
    lcd.bl.duty_u16(0)
    lcd.fill(0)
    lcd.show()
