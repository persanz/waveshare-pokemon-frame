import gc,time,machine,hashlib
from machine import Pin
power=Pin(28,Pin.OUT,value=1)
from lcd import LCD_1inch54
gc.threshold(1024)
gc.collect()
lcd=LCD_1inch54()
hashes=[]
real_show=lcd.show
def capture():
 hashes.append(hashlib.sha256(lcd.buffer).digest())
 real_show()
lcd.show=capture
import frame_app,power_screen
power_screen.suppressed=True
del power_screen
real_i2c=machine.I2C
class Bus:
 def __init__(self,*a,**kw):
  self.bus=real_i2c(*a,**kw)
  self.n=0
 def writeto_mem(self,*a): return self.bus.writeto_mem(*a)
 def readfrom_mem(self,addr,reg,n):
  if addr==0x15 and reg==2:
   self.n+=1
   if self.n>65: raise KeyboardInterrupt
   down=4<=self.n<=24 or 29<=self.n<=31
   return bytes([int(down),0,120,0,120])
  if addr==0x6b and reg==0x35: return bytes(6)
  return self.bus.readfrom_mem(addr,reg,n)
frame_app.I2C=Bus
try:
 frame_app.start(lcd,power,Pin(24,Pin.IN,Pin.PULL_UP))
except KeyboardInterrupt:
 assert len(hashes)==4, len(hashes)
 assert hashes[1]==hashes[3], 'Artwork changed after description'
 print('PASS: longpress description, tap return, identical artwork; heap',gc.mem_free())
