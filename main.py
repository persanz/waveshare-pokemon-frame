# A one-shot selection gives each app a fresh interpreter and full heap.
import gc
import os
gc.threshold(1024)
from machine import Pin
power = Pin(28, Pin.OUT, value=1)
button = Pin(24, Pin.IN, Pin.PULL_UP)
try:
    with open('/launch_once', 'r') as f:
        choice = f.read(24)
    del f
    os.remove('/launch_once')
except OSError:
    choice = ''
from lcd import LCD_1inch54
gc.collect()
lcd = LCD_1inch54()
lcd.write_cmd(0x36)
lcd.write_data(0x00)
if choice not in ('companion_app', 'frame_app'):
    import boot_splash
    boot_splash.show(lcd)
    import sys
    del sys.modules['boot_splash']
    del boot_splash
    gc.collect()
    import boot_menu
    choice = boot_menu.choose(lcd, power, button)
    with open('/launch_once', 'w') as f:
        f.write(choice)
    os.sync()
    from machine import soft_reset
    soft_reset()
print('Launching', choice)
gc.collect()
app = __import__(choice)
app.start(lcd, power, button)
