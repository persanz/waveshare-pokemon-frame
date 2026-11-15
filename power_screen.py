"""Board-specific GPIO17 power indication, verified by a cable-cycle log.

Measured high on USB, low during unplug, high after reconnect (2026-11-13).
This is not a direct VBUS signal; other charging states remain unverified.
"""
import os
import time
from machine import Pin

suppressed = False

# Temporary boot diagnostics: first ~10 s after the monitor's own module load,
# sampled every >=250 ms. ticks_ms() persists across chip resets on this board
# (RTC-based), so the window is boot-relative, not absolute.
try:
    _boot = time.ticks_ms()
except AttributeError:
    _boot = 0
_log_last = None


def _log(now, pin, mv):
    global _log_last
    if _log_last is not None and time.ticks_diff(now, _log_last) < 250:
        return
    _log_last = now
    try:
        try:
            if os.stat('/bootlog.csv')[6] > 1500:
                os.remove('/bootlog.csv')
        except OSError:
            pass
        with open('/bootlog.csv', 'a') as f:
            f.write('%d,%d,%d\r\n' % (time.ticks_diff(now, _boot), pin, mv))
    except OSError:
        pass




class Monitor:
    def __init__(self):
        self.pin = Pin(17, Pin.IN)
        self.used = suppressed
        self.since = None
        self.disconnected_since = None
        self.ladc = None

    def poll(self, lcd, bus, left, power, wdt=None, save=None):
        global suppressed
        now = time.ticks_ms()
        if time.ticks_diff(now, _boot) < 15000:
            if self.ladc is None:
                try:
                    from machine import ADC
                    self.ladc = ADC(Pin(29))
                except (OSError, ValueError):
                    pass
            mv = self.ladc.read_u16() * 9900 // 65535 if self.ladc is not None else -1
            _log(now, self.pin.value(), mv)
        if not self.pin.value():
            self.since = None
            if self.disconnected_since is None:
                self.disconnected_since = now
            elif time.ticks_diff(now, self.disconnected_since) >= 1500:
                self.used = suppressed = False
            return False
        self.disconnected_since = None
        if self.used:
            return False
        if self.since is None:
            self.since = now
        if time.ticks_diff(now, self.since) < 700:
            return False
        import gc
        import sys
        gc.collect()
        try:
            import charge_overlay
            completed = charge_overlay.run(self, lcd, bus, left, power, wdt, save)
            if completed:
                self.used = suppressed = True
            return completed
        finally:
            # A failed allocation must not consume the one-shot prompt.
            self.since = None
            if 'charge_overlay' in sys.modules:
                del sys.modules['charge_overlay']
            gc.collect()
