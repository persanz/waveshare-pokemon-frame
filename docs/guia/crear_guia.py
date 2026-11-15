"""Build the Spanish, two-sided A4 guide. Run with Pillow, numpy, reportlab.
Screen images are desktop recreations using the project's renderers and assets.
"""
from pathlib import Path
import ast, builtins, struct, sys, types, zlib
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
IMAGES=OUT/'imagenes'
IMAGES.mkdir(exist_ok=True)
FONT='/System/Library/Fonts/Supplemental/'
small=ImageFont.truetype(FONT+'Arial.ttf',9)

class LCD:
    """Desktop RGB565 adapter; each draw starts from the shared framebuffer."""
    def __init__(self): self.buffer=bytearray(115200)
    def image(self):
        v=np.frombuffer(self.buffer,dtype='>u2').reshape(240,240).astype(np.uint32)
        return Image.fromarray(np.stack((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31),axis=2).astype('uint8'))
    def put(self,im):
        a=np.array(im,dtype=np.uint16)
        v=((a[:,:,0]>>3)<<11)|((a[:,:,1]>>2)<<5)|(a[:,:,2]>>3)
        self.buffer[:]=v.astype('>u2').tobytes()
    def color(self,c):
        c=((c&255)<<8)|(c>>8)
        return ((c>>11)*255//31,((c>>5)&63)*255//63,(c&31)*255//31)
    def fill(self,c): self.buffer[:]=int(c).to_bytes(2,'little')*57600
    def shape(self,kind,xy,c,filled=False):
        im=self.image(); d=ImageDraw.Draw(im); color=self.color(c)
        if kind=='line': d.line(xy,fill=color)
        elif kind=='rectangle': d.rectangle(xy,fill=color if filled else None,outline=color)
        elif kind=='ellipse': d.ellipse(xy,fill=color if filled else None,outline=color)
        self.put(im)
    def fill_rect(self,x,y,w,h,c): self.shape('rectangle',(x,y,x+w-1,y+h-1),c,True)
    def rect(self,x,y,w,h,c): self.shape('rectangle',(x,y,x+w-1,y+h-1),c)
    def ellipse(self,x,y,rx,ry,c,filled=False): self.shape('ellipse',(x-rx,y-ry,x+rx,y+ry),c,filled)
    def line(self,x,y,x2,y2,c): self.shape('line',(x,y,x2,y2),c)
    def hline(self,x,y,w,c): self.line(x,y,x+w-1,y,c)
    def vline(self,x,y,h,c): self.line(x,y,x,y+h-1,c)
    def pixel(self,x,y,c): self.fill_rect(x,y,1,1,c)
    def text(self,text,x,y,c):
        im=self.image(); d=ImageDraw.Draw(im)
        for i,ch in enumerate(text): d.text((x+i*8,y-2),ch,font=small,fill=self.color(c))
        self.put(im)
    def show(self): pass
    def save(self,name): self.image().resize((960,960),Image.Resampling.NEAREST).save(IMAGES/(name+'.png'))

realopen=builtins.open
def asset_open(path,*args,**kw):
    if isinstance(path,str) and path.startswith('/') and (ROOT/path[1:]).exists(): path=ROOT/path[1:]
    return realopen(path,*args,**kw)
sys.path.insert(0,str(ROOT))
sys.modules['machine']=types.SimpleNamespace(Pin=None,I2C=None)
with patch('builtins.open',asset_open):
    import boot_menu,dex_description,shutdown_screen
    lcd=LCD(); boot_menu.draw(lcd); lcd.save('menu')
    lcd.buffer[:]=(ROOT/'boot_splash.dat').read_bytes()
    lcd.fill_rect(0,215,240,25,0x4100);lcd.text('Loading....',76,222,0xffff);lcd.save('inicio')
    shutdown_screen.draw(lcd);lcd.save('apagado')

def artwork(number):
    with realopen(ROOT/'pokemon_hd.dat','rb') as f:
        count=struct.unpack('<I',f.read(4))[0]
        for _ in range(count):
            dex,offset,size,name_offset=struct.unpack('<IIII',f.read(16))
            if dex==number: break
        else: raise ValueError(number)
        f.seek(offset); data=zlib.decompress(f.read(size),-10)
    assert len(data)==115200
    out=LCD();out.buffer[:]=data;return out
lcd=artwork(25)
lcd.fill_rect(0,216,240,24,0);lcd.text('25 PIKACHU',80,224,0x20fd);lcd.save('picodex')
with patch('builtins.open',asset_open):
    dex_description.show(lcd,25,'PIKACHU');lcd.save('descripcion')

# Execute the actual companion status renderer with representative care values.
from companion_state import Pet
pet=Pet(index=24,food=75,joy=80)
lcd=LCD();im=Image.new('RGB',(240,240)); im.paste(artwork(25).image().resize((152,152),Image.Resampling.NEAREST),(44,24));lcd.put(im)
source=ast.parse((ROOT/'companion_app.py').read_text())
start=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='start')
functions=[n for n in start.body if isinstance(n,ast.FunctionDef) and n.name in ('center','status')]
module=ast.Module(body=functions,type_ignores=[])
ns=dict(lcd=lcd,pet=pet,title='#25 PIKACHU',notice='',notice_until=0,WHITE=0xffff,ORANGE=0x20fd,BLACK=0,GREEN=0xe007,time=types.SimpleNamespace(ticks_ms=lambda:0,ticks_diff=lambda a,b:a-b))
exec(compile(ast.fix_missing_locations(module),'<companion-renderer>','exec'),ns)
ns['status']();lcd.save('companion')

# The charging renderer uses MicroPython's tiny monochrome glyph buffer.
class Mono:
    def __init__(self,buf,w,h,fmt): self.im=Image.new('1',(w,h));self.d=ImageDraw.Draw(self.im)
    def text(self,t,x,y,c):
        for i,ch in enumerate(t): self.d.text((x+i*8,y-2),ch,font=small,fill=c)
    def pixel(self,x,y): return self.im.getpixel((x,y))
sys.modules['framebuf']=types.SimpleNamespace(FrameBuffer=Mono,MONO_HLSB=0)
import charge_overlay
mv=3950
monitor=types.SimpleNamespace(adc=types.SimpleNamespace(read_u16=lambda:mv*65535//9900),mv=mv)
lcd=LCD();charge_overlay.draw(monitor,lcd);lcd.save('carga')

# A4 print layout: generous type, white paper, light panels and numbered actions.
pdfmetrics.registerFont(TTFont('Body',FONT+'Arial.ttf'))
pdfmetrics.registerFont(TTFont('Bold',FONT+'Arial Bold.ttf'))
pdfmetrics.registerFont(TTFont('Round',FONT+'Arial Rounded Bold.ttf'))
W,H=A4
pdf=OUT/'Guia-rapida-Pokemon-A4.pdf'
c=canvas.Canvas(str(pdf),pagesize=A4)
c.setTitle('Mi juguete Pokémon · Guía rápida A4')
c.setAuthor('Proyecto PICODEX y Virtual Pokemon')
INK=HexColor('#182739'); MUTED=HexColor('#52606B'); BLUE=HexColor('#1C5680'); GOLD=HexColor('#E7B633'); PALE=HexColor('#F4F6F8')
def text(txt,x,y,size=12,font='Body',color=INK):
    c.setFillColor(color);c.setFont(font,size);c.drawString(x,y,txt)
def paragraph(txt,x,top,width,size=12,leading=17,color=INK):
    style=ParagraphStyle('p',fontName='Body',fontSize=size,leading=leading,textColor=color)
    p=Paragraph(txt,style);_,h=p.wrap(width,H);p.drawOn(c,x,top-h);return top-h

def footer(n):
    c.setStrokeColor(HexColor('#CDD4DB'));c.line(34,42,W-34,42)
    text('PICODEX + VIRTUAL POKEMON',34,28,8,'Bold',MUTED)
    c.setFont('Body',8);c.drawRightString(W-34,28,f'{n} / 2 · A4 · Imprimir al 100 %')

def header(kicker,title,subtitle):
    text(kicker,34,H-35,9,'Bold',BLUE)
    text(title,34,H-70,27,'Round')
    text(subtitle,34,H-92,11,color=MUTED)
    c.setFillColor(GOLD);c.roundRect(34,H-109,65,4,2,fill=1,stroke=0)

def screenshot(name,x,top,size,caption=None):
    c.setFillColor(INK);c.roundRect(x-4,top-size-4,size+8,size+8,9,fill=1,stroke=0)
    c.drawImage(ImageReader(str(IMAGES/(name+'.png'))),x,top-size,size,size)
    if caption: paragraph(caption,x,top-size-11,size,9,12,MUTED)

def step(n,title,body,x,top,width):
    c.setFillColor(BLUE);c.circle(x+10,top-9,10,fill=1,stroke=0)
    text(str(n),x+7,top-13,11,'Bold',white)
    text(title,x+28,top-13,14,'Bold')
    return paragraph(body,x+28,top-24,width-28,12,17)

def band(title,body,top,height=61):
    c.setFillColor(PALE);c.roundRect(34,top-height,W-68,height,8,fill=1,stroke=0)
    text(title,47,top-19,12,'Bold',BLUE)
    paragraph(body,47,top-27,W-94,10.5,14)

header('GUÍA RÁPIDA · CARA 1','¡Empieza tu aventura!','Dos mundos para jugar: explorar Pokémon y cuidar de un amigo.')
screenshot('menu',40,710,138)
step(1,'Enciende y elige','Pulsa el <b>botón izquierdo</b> para encender. Espera unos <b>5 segundos</b>.',202,710,350)
paragraph('En el menú, toca:<br/><b>Pikachu</b> → Virtual Pokemon.<br/><b>Pokédex rojo</b> → PICODEX.',230,634,320,12,18)
paragraph('Si aparece la batería, tócala para continuar.',202,579,350,11,15,BLUE)
text('PICODEX: descubre sus secretos',34,532,20,'Round')
screenshot('picodex',84,508,145)
screenshot('descripcion',357,508,145)
# Text aligned in two clearly separate columns under each screen.
text('2  Mira otros Pokémon',38,337,14,'Bold')
paragraph('Toca el <b>lado izquierdo</b> para ir atrás y el <b>lado derecho</b> para avanzar.<br/><br/>También puedes usar los botones izquierdo y derecho.',38,321,240,12,17)
text('3  Abre su descripción',307,337,14,'Bold')
paragraph('Mantén el dedo en el <b>centro del dibujo 1 segundo</b>.<br/><br/>Toca para pasar de página. En la última, toca otra vez para <b>volver al dibujo</b>.',307,321,247,12,17)
band('¡Sorpresa! Un Pokémon diferente','Mueve el juguete suavemente. Déjalo quieto un momento antes de volver a moverlo.',186,62)
paragraph('<b>Truco:</b> en PICODEX, mantén el botón derecho unos 2 segundos para volver al primer Pokémon.',38,108,W-76,11,15)
footer(1);c.showPage()

header('GUÍA RÁPIDA · CARA 2','¡Cuida de tu Pokémon!','Tu compañero necesita comida, cariño y ganas de jugar.')
screenshot('companion',40,710,140)
step(4,'Haz feliz a tu amigo','<b>COMIDA</b>: dale de comer.<br/><b>CARICIA</b>: dale cariño.<br/><b>JUGAR</b>: diviértete con él.',205,710,350)
paragraph('También puedes tocar el dibujo para acariciarlo.<br/><b>Botón izquierdo:</b> comida.<br/><b>Botón derecho:</b> jugar.',233,607,318,11.5,16)
paragraph('Mira las barras de COMIDA y ÁNIMO. Si tiene hambre, dale comida antes de jugar.',40,546,W-80,11.5,16)
band('¿Quieres conocer a otro amigo?','Mueve el juguete suavemente: aparecerá otro compañero. Si quieres seguir con el mismo, evita agitarlo.',493,61)
screenshot('carga',40,405,118)
step(5,'Carga y sigue jugando','Con ayuda de un adulto, conecta el cable USB. Cuando aparezca la batería, <b>toca cualquier lugar</b> para volver a tu juego.',184,406,370)
# Colour legend includes words and thresholds so it works in grayscale.
paragraph('<b>Rojo:</b> menos del 20 %.<br/><b>Naranja:</b> del 20 al 69 %.<br/><b>Verde:</b> del 70 al 100 %.',212,319,340,11,15)
screenshot('apagado',40,243,101)
step(6,'Apaga o cambia de mundo','Mantén el <b>botón izquierdo unos 2 segundos</b>. Espera a ver <b>GOODBYE!</b> (¡adiós!).',169,243,385)
paragraph('Para elegir otro mundo: desconecta el USB, apaga y vuelve a encender. Apaga así también para guardar los cuidados de tu compañero.',197,171,356,10.5,14)
paragraph('<b>Para la persona adulta:</b> el porcentaje de batería es orientativo. Con USB, el aparato puede seguir alimentado aunque la pantalla esté apagada. No retires la tarjeta SD durante el uso.',35,111,W-70,9,12,MUTED)
paragraph('Imágenes recreadas con el código y los gráficos del proyecto; no son fotografías de la placa. El texto de pantalla usa una tipografía aproximada. Pokémon pertenece a sus titulares.',35,67,W-70,7.2,9,MUTED)
footer(2);c.save()
print(pdf)
