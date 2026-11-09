# Allocate the large display buffer before loading the slideshow.
import gc
from machine import Pin
power = Pin(28, Pin.OUT, value=1)
button = Pin(24, Pin.IN, Pin.PULL_UP)
from lcd import LCD_1inch54
gc.collect()
lcd = LCD_1inch54()
lcd.write_cmd(0x36)
lcd.write_data(0x00)
import frame_app
frame_app.start(lcd, power, button)
