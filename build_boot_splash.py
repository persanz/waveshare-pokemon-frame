"""Render downloaded Wikimedia assets to the display's native RGB565 format.
Run: uv run --with pillow --with resvg-py python build_boot_splash.py
"""
from pathlib import Path
from io import BytesIO
import math, random, struct
import resvg_py
from PIL import Image, ImageDraw, ImageFilter

S=960
canvas=Image.new('RGB',(S,S))
pixels=canvas.load()
for y in range(S):
    for x in range(S):
        glow=max(0,1-math.hypot((x-480)/660,(y-490)/700))
        pixels[x,y]=(int(4+5*glow),int(9+20*glow),int(21+40*glow))
canvas=canvas.convert('RGBA')
halo=Image.new('RGBA',(S,S));d=ImageDraw.Draw(halo)
d.ellipse((190,320,770,900),outline=(44,157,255,165),width=16)
d.ellipse((240,370,720,850),outline=(255,202,45,70),width=8)
canvas=Image.alpha_composite(canvas,halo.filter(ImageFilter.GaussianBlur(24)))
d=ImageDraw.Draw(canvas)
random.seed(25)
for _ in range(38):
    x=random.randrange(30,930);y=random.randrange(25,850)
    r=random.choice((2,3,4))
    d.ellipse((x-r,y-r,x+r,y+r),fill=(125,192,255,170))
for x,y in ((100,350),(840,386),(172,710),(812,740)):
    d.line((x-10,y,x+10,y),fill=(255,218,105),width=3)
    d.line((x,y-10,x,y+10),fill=(255,218,105),width=3)
root=Path('assets/splash')
logo=Image.open(BytesIO(resvg_py.svg_to_bytes(svg_path=str(root/'pokemon-logo.svg'),width=864))).convert('RGBA')
ball=Image.open(BytesIO(resvg_py.svg_to_bytes(svg_path=str(root/'pokeball.svg'),width=424))).convert('RGBA')
canvas.alpha_composite(logo,((S-logo.width)//2,64))
canvas.alpha_composite(ball,((S-ball.width)//2,388))
ImageDraw.Draw(canvas).rectangle((0,860,960,960),fill=(4,9,21))
canvas=canvas.convert('RGB').resize((240,240),Image.Resampling.LANCZOS)
canvas.save(root/'boot-splash.png')
raw=bytearray()
for r,g,b in canvas.getdata():
    v=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
    raw.extend(struct.pack('>H',v))
Path('boot_splash.dat').write_bytes(raw)
print('Splash ready:',len(raw),'bytes')
