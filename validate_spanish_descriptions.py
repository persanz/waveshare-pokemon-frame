"""Check Spanish coverage, pagination, provenance and preserved English files."""
import hashlib
import json
import struct
from pathlib import Path
from dex_description import lookup, lines

def main():
    original = json.loads(Path('pokemon_descriptions.json').read_text())['pokemon']
    spanish = json.loads(Path('pokemon_descriptions_es.json').read_text())['pokemon']
    assert len(original) == len(spanish) == 1538
    for en, es in zip(original, spanish):
        for key in en:
            if key not in ('description', 'genus'):
                assert en[key] == es[key], (key, en['id'])
        assert es['description'].strip() and es['genus'].strip()
    archive = Path('pokemon_hd.dat').read_bytes()
    count, = struct.unpack_from('<I', archive)
    assert count == 1538
    max_pages = 0
    allowed = set('áéíóúÁÉÍÓÚñÑüÜ¡¿°º')
    unsupported = set()
    for i in range(count):
        number, = struct.unpack_from('<I', archive, 4+i*16)
        text = lookup(number, 'pokemon_descriptions_es.bin')
        assert text != 'Descripcion no disponible.', number
        wrapped = list(lines(text, 28))
        assert all(len(line) <= 28 for line in wrapped)
        assert ''.join(''.join(wrapped).split()) == ''.join(text.split()), number
        pages = [wrapped[j:j+14] for j in range(0,len(wrapped),14)]
        assert sum(pages, []) == wrapped
        max_pages = max(max_pages, len(pages))
        unsupported.update(c for c in text if ord(c)>127 and c not in allowed)
    assert not unsupported, unsupported
    for name, digest in json.loads(Path('description-sources/english-original-sha256.json').read_text()).items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    from collections import Counter
    print('Validated', count, 'archive IDs; max pages:', max_pages)
    print('Provenance:', dict(Counter(r['translation_method'] for r in spanish)))
    print('English SHA256 checks passed; all characters renderable.')

if __name__ == '__main__':
    main()
