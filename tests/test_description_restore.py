"""Exercise the actual nested snapshot helpers without importing board drivers."""
import ast
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse((Path(__file__).resolve().parents[1] / 'frame_app.py').read_text())
        start = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
        helpers = [n for n in start.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('cache_artwork', 'restore_artwork')]
        factory = ast.parse('''
def factory(lcd, os):
 description_open = True
 def is_reading():
  return description_open
 return cache_artwork, restore_artwork, is_reading
''')
        factory.body[0].body[1:1] = helpers
        namespace = {}
        exec(compile(ast.fix_missing_locations(factory), '<snapshot-helpers>', 'exec'), namespace)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'snapshot'
        real_open = open
        self.open_patch = patch('builtins.open', lambda path, *a, **kw: real_open(
            self.path if path == '/picodex-return.tmp' else path, *a, **kw))
        self.open_patch.start()
        self.addCleanup(self.open_patch.stop)
        self.shows = 0
        def show():
            self.shows += 1
        self.lcd = types.SimpleNamespace(buffer=bytearray(range(256))*450, show=show)
        self.cache, self.restore, self.is_reading = namespace['factory'](
            self.lcd, types.SimpleNamespace(remove=lambda path: os.remove(self.path)))

    def test_return_restores_all_pixels_without_decoder(self):
        original = bytes(self.lcd.buffer)
        self.cache()
        self.lcd.buffer[:] = bytes(len(original))
        self.restore()
        self.assertEqual(self.lcd.buffer, original)
        self.assertFalse(self.is_reading())
        self.assertEqual(self.shows, 1)
        self.assertFalse(self.path.exists())

    def test_incomplete_snapshot_keeps_reading_state_and_does_not_show(self):
        self.path.write_bytes(b'incomplete')
        with self.assertRaises(OSError):
            self.restore()
        self.assertTrue(self.is_reading())
        self.assertEqual(self.shows, 0)
