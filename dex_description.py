"""Read just the requested artwork's description without loading the database."""
import struct


def lookup(number, path='/pokemon_descriptions_es.bin'):
    with open(path, 'rb') as f:
        raw = f.read(4)
        if len(raw) != 4:
            raise OSError('Description header missing')
        lo, hi = 0, struct.unpack('<I', raw)[0] - 1
        while lo <= hi:
            mid = (lo + hi)//2
            f.seek(4 + mid*12)
            raw = f.read(12)
            if len(raw) != 12:
                raise OSError('Description index incomplete')
            key, offset, size = struct.unpack('<III', raw)
            if key == number:
                f.seek(offset)
                raw = f.read(size)
                if len(raw) != size:
                    raise OSError('Description incomplete')
                return raw.decode('utf-8')
            if key < number:
                lo = mid + 1
            else:
                hi = mid - 1
    return 'Descripcion no disponible.'


def lines(text, width=28):
    line = ''
    for word in text.split():
        if line and len(line)+len(word)+1 > width:
            yield line
            line = ''
        while len(word) > width:
            yield word[:width]
            word = word[width:]
        if word:
            line = (line+' '+word) if line else word
    if line:
        yield line


def text_es(lcd, text, x, y):
    # Add Spanish accents to the built-in ASCII font using small pixel marks.
    accents = 'áéíóúÁÉÍÓÚ'
    bases = 'aeiouAEIOU'
    for char in text:
        if char in accents:
            lcd.text(bases[accents.index(char)], x, y, 0xffff)
            lcd.line(x+3, y-2, x+5, y-3, 0xffff)
        elif char in 'ñÑ':
            lcd.text('n' if char == 'ñ' else 'N', x, y, 0xffff)
            lcd.line(x+2, y-2, x+3, y-3, 0xffff)
            lcd.line(x+3, y-3, x+5, y-2, 0xffff)
            lcd.pixel(x+6, y-3, 0xffff)
        elif char in 'üÜ':
            lcd.text('u' if char == 'ü' else 'U', x, y, 0xffff)
            lcd.pixel(x+2, y-2, 0xffff)
            lcd.pixel(x+5, y-2, 0xffff)
        elif char in '°º':
            lcd.ellipse(x+4, y+1, 1, 1, 0xffff)
        elif char == '¡':
            lcd.pixel(x+3, y, 0xffff)
            lcd.vline(x+3, y+2, 5, 0xffff)
        elif char == '¿':
            lcd.pixel(x+3, y, 0xffff)
            lcd.vline(x+3, y+2, 2, 0xffff)
            lcd.line(x+3, y+3, x+1, y+5, 0xffff)
            lcd.hline(x+2, y+7, 4, 0xffff)
        else:
            lcd.text(char if ord(char)<128 else '?', x, y, 0xffff)
        x += 8


def show(lcd, number, name, page=0):
    import gc
    gc.collect()
    try:
        text = lookup(number)
    except (OSError, ValueError) as e:
        print('Description error:', e)
        text = 'Descripción no disponible. Revisa los archivos.'
    wrapped = list(lines(text))
    pages = max(1, (len(wrapped)+13)//14)
    page = min(max(0, page), pages-1)
    lcd.fill(0)
    text_es(lcd, name[:28], 8, 10)
    lcd.hline(8, 28, 224, 0xffff)
    y = 44
    for line in wrapped[page*14:(page+1)*14]:
        text_es(lcd, line, 8, y)
        y += 12
    if pages > 1:
        lcd.text('%d/%d' % (page+1, pages), 8, 224, 0xffff)
    label = 'TOCA PARA SEGUIR' if page+1<pages else 'TOCA PARA VOLVER'
    lcd.text(label, 60, 224, 0xffff)
    lcd.show()
    print('PICODEX description:', number, 'page', page+1)
    return pages
