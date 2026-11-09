#!/usr/bin/env python3
"""Build higher-resolution Pokemon sprite archive with embedded display names.

Sources: official artwork PNGs + PokeAPI-verified names (produced by /tmp/gen_labels.py).
Output format (new, incompatible with the old 160x160 archive):
  u32 count
  count x entries of 16 bytes: (dex_num u32, offset u32, size u32, name_offset u32)
  [compressed raw-DEFLATE RGB565 blobs, 240x240 each, 1 KiB window]
  [name blob: concatenated null-terminated UTF-8 strings]
Sprites are 240x240 native (matches the 240x240 screen) so the board draws them
1:1 with no upscale, giving full physical resolution.
"""
from pathlib import Path
from PIL import Image
import io, struct, zlib, json

SRC = Path('/tmp/pokemon-sprites/sprites/pokemon/other/official-artwork')
LABELS = Path('/tmp/art_labels.json')
OUT = Path(__file__).parent / 'pokemon_hd.dat'

CANVAS = 240  # match screen physical resolution

labels = json.load(open(LABELS))

def sortkey(p):
    stem = p.stem
    base = stem.split('-')[0]
    try:
        return (int(base), stem)
    except ValueError:
        return (0, stem)
files = sorted(SRC.glob('*.png'), key=sortkey)
out_path = OUT
with out_path.open('wb') as f:
    f.write(struct.pack('<I', len(files)))
    # reserve space for entries
    f.write(b'\0' * (len(files) * 16))
    entries = []
    names = bytearray()
    for p in files:
        stem = p.stem
        im = Image.open(p).convert('RGBA')
        bbox = im.getchannel('A').getbbox()
        if bbox:
            im = im.crop(bbox)
        # scale to fit within canvas while preserving aspect
        im.thumbnail((CANVAS, CANVAS), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (CANVAS, CANVAS), (0,0,0,255))
        canvas.alpha_composite(im, ((CANVAS-im.width)//2, (CANVAS-im.height)//2))
        # to RGB565
        data = bytearray()
        for r,g,b,_ in canvas.getdata():
            v = ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)
            data.append(v >> 8); data.append(v & 255)
        compressed = zlib.compress(bytes(data), 9, wbits=-10)
        num = 0
        try:
            num = int(stem.split('-')[0])
        except Exception:
            pass
        # name (offset filled after we know name-section base)
        name = labels.get(stem, stem).encode('utf-8')
        name_offset = len(names)
        names += name + b'\0'
        entries.append((num, f.tell(), len(compressed), name_offset))
        f.write(compressed)
    # write entries
    f.seek(4)
    for row in entries:
        f.write(struct.pack('<IIII', *row))
    # append name section; record its absolute base, patch entries
    f.seek(0, 2)
    name_base = f.tell()
    f.write(bytes(names))
    # patch absolute name offsets
    f.seek(4)
    for row in entries:
        f.write(struct.pack('<IIII', row[0], row[1], row[2], name_base + row[3]))
    print('name section base', name_base)

print('Prepared %d sprites (%dx%d); %d bytes' % (len(files), CANVAS, CANVAS, out_path.stat().st_size))
