"""Pack the existing description database for low-memory indexed lookup."""
import json
import struct
import unicodedata
from pathlib import Path

def build(source='pokemon_descriptions.json', output='pokemon_descriptions.bin', encoding='ascii'):
    records = json.loads(Path(source).read_text())['pokemon']
    by_id = {}
    for record in sorted(records, key=lambda p: ('-' in p['id'], p['id'])):
        key = int(record['id'].split('-')[0])
        if key not in by_id:
            by_id[key] = record
    entries = [by_id[key] for key in sorted(by_id)]
    offset = 4 + len(entries)*12
    table, bodies = bytearray(struct.pack('<I', len(entries))), bytearray()
    for entry in entries:
        text = ' '.join(entry['description'].replace('\u2019', "'").split())
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore') if encoding == 'ascii' else text.encode(encoding)
        table.extend(struct.pack('<III', int(entry['id'].split('-')[0]), offset, len(text)))
        bodies.extend(text)
        offset += len(text)
    Path(output).write_bytes(table + bodies)
    print('Packed', len(entries), 'descriptions:', offset, 'bytes')
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='pokemon_descriptions.json')
    parser.add_argument('--output', default='pokemon_descriptions.bin')
    parser.add_argument('--encoding', default='ascii', choices=['ascii','utf-8'])
    args = parser.parse_args()
    build(args.source, args.output, args.encoding)
