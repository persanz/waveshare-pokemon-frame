import gc,time,machine
from machine import Pin
latch=Pin(28,Pin.OUT,value=1)
class Power:
 off=False
 def value(self,v):
  if v==0:
   self.off=True
   raise KeyboardInterrupt
power=Power()
from lcd import LCD_1inch54
gc.threshold(1024)
gc.collect()
lcd=LCD_1inch54()
import frame_app,power_screen
power_screen.suppressed=True
del power_screen
real_i2c=machine.I2C
class Bus:
 reads=0
 def __init__(self,*a,**kw):
  self.bus=real_i2c(*a,**kw)
  self.n=0
 def writeto_mem(self,*a): return self.bus.writeto_mem(*a)
 def readfrom_mem(self,addr,reg,n):
  if addr==0x15 and reg==2:
   self.n+=1
   Bus.reads=self.n
   if self.n>150: raise AssertionError("Power hold ignored")
   if self.n>=40: raise OSError("Injected touch failure")
   down=4<=self.n<=24
   return bytes([int(down),0,120,0,120])
  if addr==0x6b and reg==0x35: return bytes(6)
  return self.bus.readfrom_mem(addr,reg,n)
frame_app.I2C=Bus
class Left:
 def value(self): return 0 if Bus.reads>=40 else 1
real_pin=Pin
class Pins:
 OUT=real_pin.OUT
 IN=real_pin.IN
 PULL_UP=real_pin.PULL_UP
 def __new__(cls,n,*a,**kw):
  return Left() if n==24 else real_pin(n,*a,**kw)
frame_app.Pin=Pins
try:
 frame_app.start(lcd,power,Pin(24,Pin.IN,Pin.PULL_UP))
except KeyboardInterrupt:
 assert power.off, 'Power latch not released'
 print('PASS: long-left shutdown despite repeated touch failures')
