import importlib
import sys
import types
import unittest
from unittest.mock import patch


class PowerTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0
        self.status = 1
        owner = self
        class Pin:
            IN = PULL_UP = 0
            def __init__(self, *args): pass
            def value(self): return owner.status
        class ADC:
            def __init__(self, *args): pass
            def read_u16(self): return 25155
        self.mods = patch.dict(sys.modules, {'machine': types.SimpleNamespace(Pin=Pin, ADC=ADC)})
        self.mods.start()
        sys.modules.pop('power_screen', None)
        self.p = importlib.import_module('power_screen')
        self.overlay = importlib.import_module('charge_overlay')

    def tearDown(self):
        self.mods.stop()
        sys.modules.pop('power_screen', None)

    def test_curve_bounds_and_absent_battery(self):
        for voltage in (0, 1040, 2499, 4351, 9900):
            self.assertIsNone(self.overlay.percentage(voltage))
        values = [self.overlay.percentage(v) for v in range(2500, 4351)]
        self.assertEqual(values, sorted(values))
        self.assertEqual((min(values), max(values)), (0, 100))
        self.assertEqual(self.overlay.percentage(3640), 50)
        self.assertEqual(self.overlay.percentage(4020), 100)
        self.assertEqual(self.overlay.percentage(4100), 100)

    def test_same_connection_never_reopens_or_implies_full(self):
        monitor = self.p.Monitor()
        monitor.used = True
        with patch.object(self.p.time, 'ticks_ms', lambda: self.clock, create=True), patch.object(self.p.time, 'ticks_diff', lambda a,b: a-b, create=True):
            for tick in (0, 1000, 5000):
                self.clock = tick
                self.assertFalse(monitor.poll(None, None, None, None))
        monitor.adc = types.SimpleNamespace(read_u16=lambda: 25155)
        monitor.mv = None
        self.assertLess(self.overlay.level(monitor), 100)

    def test_short_status_pulse_does_not_open(self):
        monitor = self.p.Monitor()
        with patch.object(self.p.time, 'ticks_ms', lambda: self.clock, create=True), patch.object(self.p.time, 'ticks_diff', lambda a,b: a-b, create=True):
            self.assertFalse(monitor.poll(None, None, None, None))
            self.clock = 650
            self.assertFalse(monitor.poll(None, None, None, None))
            self.status = 0
            self.assertFalse(monitor.poll(None, None, None, None))
            self.assertIsNone(monitor.since)

    def test_smoothing(self):
        m = self.p.Monitor()
        m.adc = types.SimpleNamespace(read_u16=lambda: 25155)
        m.mv = None
        self.overlay.level(m)
        initial = m.mv
        m.adc.read_u16 = lambda: 27000
        self.overlay.level(m)
        self.assertGreater(m.mv, initial)
        self.assertLess(m.mv, 27000*9900//65535)

    def test_failed_overlay_does_not_consume_prompt(self):
        monitor = self.p.Monitor()
        now = [800]
        module = types.SimpleNamespace(run=lambda *args: (_ for _ in ()).throw(MemoryError()))
        with patch.object(self.p.time, 'ticks_ms', lambda: now[0], create=True), patch.object(self.p.time, 'ticks_diff', lambda a,b: a-b, create=True):
            monitor.since = 0
            with patch.dict(sys.modules, {'charge_overlay': module}):
                with self.assertRaises(MemoryError):
                    monitor.poll(None, None, None, None)
            self.assertFalse(monitor.used)
            self.assertFalse(self.p.suppressed)
            self.assertIsNone(monitor.since)
            self.assertFalse(monitor.poll(None, None, None, None))
            now[0] += 800
            module.run = lambda *args: True
            with patch.dict(sys.modules, {'charge_overlay': module}):
                self.assertTrue(monitor.poll(None, None, None, None))
            self.assertTrue(monitor.used)
            self.assertTrue(self.p.suppressed)
            self.assertFalse(monitor.poll(None, None, None, None))

    def test_debounced_disconnect_rearms_for_reconnect(self):
        monitor = self.p.Monitor()
        monitor.used = self.p.suppressed = True
        with patch.object(self.p.time, 'ticks_ms', lambda: self.clock, create=True), patch.object(self.p.time, 'ticks_diff', lambda a,b: a-b, create=True):
            self.status = 0
            self.assertFalse(monitor.poll(None, None, None, None))
            self.clock = 1000
            self.assertFalse(monitor.poll(None, None, None, None))
            self.assertTrue(monitor.used)
            self.status = 1
            self.assertFalse(monitor.poll(None, None, None, None))
            self.status = 0
            self.clock = 2000
            self.assertFalse(monitor.poll(None, None, None, None))
            self.clock = 3600
            self.assertFalse(monitor.poll(None, None, None, None))
            self.assertFalse(monitor.used)
            self.assertFalse(self.p.suppressed)
            self.status = 1
            self.assertFalse(monitor.poll(None, None, None, None))
            self.clock = 4400
            with patch.dict(sys.modules, {'charge_overlay': types.SimpleNamespace(run=lambda *args: True)}):
                self.assertTrue(monitor.poll(None, None, None, None))
            self.assertTrue(monitor.used)
