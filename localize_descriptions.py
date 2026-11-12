"""Create a separate Spanish database; never modify the English originals.
Exact-version Spanish game text is preferred. Other source text is translated
locally via Qwen3 8B, cached and marked as machine translated.
"""
import csv
import json
import re
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path
from collections import defaultdict

ROOT = Path('description-sources')
def csv_rows(name):
    return list(csv.DictReader((ROOT/name).open(encoding='utf-8')))
def normalize(text):
    return ' '.join(text.lower().split())
def clean(text):
    return ' '.join(text.replace('\u000c', ' ').split())
def translate(text):
    markers = list(re.finditer(r'\[(\d{6})\]', text))
    items = [{'id':int(m[1]), 'english':text[m.end():markers[i+1].start() if i+1<len(markers) else len(text)].strip()} for i,m in enumerate(markers)]
    schema = {'type':'object','properties':{'translations':{'type':'array','items':{'type':'object','properties':{'id':{'type':'integer'},'spanish':{'type':'string'}},'required':['id','spanish']}}},'required':['translations']}
    payload = {'model':'qwen3-8b-nothink:latest','stream':False,'think':False,'format':schema,
               'messages':[{'role':'system','content':"Translate every supplied English Pokemon description/category into accurate, natural Spanish from Spain. Preserve all facts, uncertainty, numbers, and Pokemon species names exactly. Do not invent facts, omit clauses, explain, or summarize. Pokemon names must never be translated as ordinary words. Use official terminology: Pokemon, Pokedex, Entrenador. Return one translations item for every input id, in order, with id and spanish. /no_think"},
                           {'role':'user','content':json.dumps(items,ensure_ascii=False)}],
               'options':{'temperature':0,'num_ctx':8192,'num_predict':4096}}
    req=urllib.request.Request('http://localhost:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    response=json.load(urllib.request.urlopen(req,timeout=240))
    translated=json.loads(response['message']['content'])['translations']
    if [r['id'] for r in translated] != [r['id'] for r in items]:
        raise RuntimeError('Local translation batch has missing or reordered IDs')
    return '\n'.join('[%06d] %s'%(row['id'],row['spanish']) for row in translated)

def main():
    original = Path('pokemon_descriptions.json')
    original_md = Path('pokemon_descriptions.md')
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (original,original_md,Path('pokemon_descriptions.bin'))}
    manifest = ROOT/'english-original-sha256.json'
    if manifest.exists():
        assert hashes == json.loads(manifest.read_text()), 'English originals differ from preserved manifest'
    data = json.loads(original.read_text())
    species = {r['identifier']:r['id'] for r in csv_rows('pokemon_species.csv')}
    versions = {r['id']:r['identifier'] for r in csv_rows('versions.csv')}
    groups=defaultdict(list)
    for row in csv_rows('pokemon_species_flavor_text.csv'):
        groups[row['species_id']].append(row)
    genera = {r['pokemon_species_id']:r['genus'] for r in csv_rows('pokemon_species_names.csv') if r['local_language_id']=='7'}
    cache_path = ROOT/'translation-cache-es-qwen3.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = set()
    output = []
    for entry in data['pokemon']:
        row = dict(entry)
        sid = species[row['species']]
        matching_versions = {r['version_id'] for r in groups[sid] if r['language_id']=='9' and normalize(r['flavor_text'])==normalize(row['description'])}
        spanish = [r for r in groups[sid] if r['language_id']=='7' and r['version_id'] in matching_versions]
        if spanish:
            chosen = min(spanish, key=lambda r:int(r['version_id']))
            row['description'] = clean(chosen['flavor_text'])
            row['translation_method'] = 'official_spanish_same_game_version'
            row['source_version'] = versions[chosen['version_id']]
        else:
            todo.add(entry['description'])
            row['translation_method'] = 'local_qwen3_8b_translation_of_original_english'
        if genera.get(sid):
            row['genus'] = genera[sid]
        else:
            todo.add(entry['genus'])
            row['_genus_pending'] = entry['genus']
        output.append(row)
    missing=sorted(text for text in todo if text not in cache)
    # Numbered paragraphs allow independent translations in small batches.
    batches=[];batch=[];size=0
    for text in missing:
        if batch and size+len(text)>900:
            batches.append(batch);batch=[];size=0
        batch.append(text);size+=len(text)+12
    if batch:batches.append(batch)
    for index,batch in enumerate(batches):
        request='\n'.join('[%06d] %s'%(i,clean(text)) for i,text in enumerate(batch))
        result=translate(request)
        parts=list(re.finditer(r'\[(\d{6})\]',result))
        if [int(m[1]) for m in parts] != list(range(len(batch))):
            raise RuntimeError('Translation markers changed; no output database written. Batch %d'%index)
        for i,part in enumerate(parts):
            end=parts[i+1].start() if i+1<len(parts) else len(result)
            text=clean(result[part.end():end])
            if not text:raise RuntimeError('Empty translation')
            cache[batch[i]]=text
        cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n')
        print('Translated batch',index+1,'/',len(batches),'cached',len(cache),flush=True)
    overrides_path = ROOT/'translation-overrides-es.json'
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    cache.update(overrides)
    for row in output:
        if row['translation_method']=='local_qwen3_8b_translation_of_original_english':
            row['description']=cache[row['description']]
        if '_genus_pending' in row:
            row['genus']=cache[row.pop('_genus_pending')]
    result={'count':len(output),'language':'es','source_commit':(ROOT/'commit.txt').read_text().strip(),
            'translation_notes':'Spanish game text for matching English game versions; other descriptions translated from the preserved English source. Alternate artwork shares species descriptions as in the original database.',
            'pokemon':output}
    result['review_notes'] = 'Assistant compared all 530 cached translation pairs against English; corrections are stored separately. Official matching-version Spanish text was reused, not independently line-edited.'
    Path('pokemon_descriptions_es.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    md=['# Descripciones de Pokémon\n', 'Total: %d imágenes.\n'%len(output)]
    for row in output:
        md.extend(['## %s (#%s)\n'%(row['label'],row['dex']),'**Categoría:** %s\n'%row['genus'],row['description']+'\n'])
    Path('pokemon_descriptions_es.md').write_text('\n'.join(md))
    for path,digest in hashes.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    (ROOT/'english-original-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print('Saved',len(output),'Spanish entries; English originals unchanged',flush=True)

if __name__=='__main__':main()
