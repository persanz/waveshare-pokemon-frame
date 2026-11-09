"""Audio support for the Waveshare RP2350-Touch-LCD-1.54.

Hardware (from Waveshare's official C example):
  ES8311 codec on I2C1 SDA=6 SCL=7 (address 0x18)
  MCLK=3, BCLK=4, LRCLK=5 (I2S)
  DOUT=1 (sample data out), DIN=2 (microphone)
  Amplifier enable NS4150B = GPIO0

Tones are generated as 16-bit mono sine waves and streamed via machine.I2S.
All calls are wrapped so a failure never breaks the slideshow.
"""

import math
import time
import rp2
from machine import Pin, I2C, I2S

ES8311_ADDR = 0x18
PA_CTRL_PIN = 0
DOUT_PIN = 1
BCLK_PIN = 4
LRCLK_PIN = 5

# Key ES8311 registers (derived from the ES8311 driver).
REG_RESET = 0x00
REG_CLK_DIV1 = 0x02
REG_CLK_DIV2 = 0x03
REG_ADC_CTRL1 = 0x06
REG_MIC_CTRL1 = 0x09
REG_DAC_CTRL1 = 0x0D
REG_SDP_IN_FMT = 0x11
REG_SDP_OUT_FMT = 0x12
REG_DAC_VOL = 0x15
REG_ADC_VOL = 0x16
REG_SYSTEM_CTRL = 0x14
REG_ANALOG_SYS = 0x43
REG_ANALOG_DAC = 0x53

SAMPLE_RATE = 24000


class Audio:
    def __init__(self):
        self.i2c = None
        self.pa = None
        self.i2s = None
        self.mclk_sm = None
        self.ok = False
        try:
            self.pa = Pin(PA_CTRL_PIN, Pin.OUT, value=0)
            self.i2c = I2C(1, sda=Pin(6), scl=Pin(7), freq=100000)
            if not self._init_codec():
                return
            self.i2s = I2S(0,
                           sck=Pin(BCLK_PIN), ws=Pin(LRCLK_PIN),
                           sd=Pin(DOUT_PIN),
                           mode=I2S.TX, bits=16, format=I2S.MONO,
                           rate=SAMPLE_RATE, ibuf=2000)
            self._start_mclk()
            self.pa.value(1)
            self.ok = True
        except Exception as e:
            print('Audio init failed:', e)
            self.ok = False

    def _start_mclk(self):
        # Generate MCLK on GPIO3 via PIO (ES8311 needs a master clock).
        try:
            @rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
            def _mclk_prog():
                set(pins, 1)
                nop()
                set(pins, 0)
                nop()
            self.mclk_sm = rp2.StateMachine(1, _mclk_prog,
                                            freq=125_000_000,
                                            set_base=Pin(3))
            self.mclk_sm.active(1)
        except Exception as e:
            print('MCLK fail:', e)

    def _write_reg(self, reg, val):
        if self.i2c is None:
            return
        self.i2c.writeto_mem(ES8311_ADDR, reg, bytes([val]))

    def _init_codec(self):
        try:
            self._write_reg(REG_RESET, 0x00)
            time.sleep_ms(20)
            self._write_reg(REG_CLK_DIV1, 0x10)
            self._write_reg(REG_CLK_DIV2, 0x01)
            self._write_reg(REG_ANALOG_SYS, 0x08)
            self._write_reg(REG_ANALOG_DAC, 0x0C)
            self._write_reg(REG_DAC_CTRL1, 0xA0)
            self._write_reg(REG_ADC_CTRL1, 0xA0)
            self._write_reg(REG_MIC_CTRL1, 0x20)
            self._write_reg(REG_SDP_IN_FMT, 0x30)
            self._write_reg(REG_SDP_OUT_FMT, 0x30)
            self._write_reg(REG_SYSTEM_CTRL, 0x00)
            self._write_reg(REG_DAC_VOL, 0x3C)
            self._write_reg(REG_ADC_VOL, 0x3C)
            self.pa.value(1)
            return True
        except Exception as e:
            print('ES8311 init failed:', e)
            return False

    def _sine(self, freq, start, count):
        samples = bytearray(count * 2)
        scale = 1 << 14  # ~50% amplitude
        for i in range(count):
            v = int(scale * math.sin(2 * math.pi * freq * (start + i) / SAMPLE_RATE))
            samples[2 * i] = v & 0xFF
            samples[2 * i + 1] = (v >> 8) & 0xFF
        return samples

    def play_tone(self, freq=880, duration_ms=120):
        if not self.ok or self.i2s is None:
            return
        try:
            n = int(SAMPLE_RATE * duration_ms // 1000)
            CHUNK = 512  # small buffers to stay within heap
            pos = 0
            while pos < n:
                cnt = min(CHUNK, n - pos)
                data = self._sine(freq, pos, cnt)
                self.i2s.write(data)
                pos += cnt
            # Stop output and release the I2S to avoid a continuous tone / hang.
            self.stop()
        except Exception as e:
            print('tone err', e)

    def stop(self):
        try:
            if self.mclk_sm is not None:
                self.mclk_sm.active(0)
                self.mclk_sm = None
            if self.i2s is not None:
                self.i2s.deinit()
                self.i2s = None
            if self.pa is not None:
                self.pa.value(0)
        except Exception:
            pass

    def power_on_chime(self):
        self.play_tone(1046, 90)
        time.sleep_ms(60)
        self.play_tone(1318, 140)

    def power_off_chime(self):
        self.play_tone(880, 120)
        time.sleep_ms(40)
        self.play_tone(659, 140)
