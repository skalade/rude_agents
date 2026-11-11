#!/usr/bin/env python3
"""Validate report inputs, local links, and basic STE sentence limits."""
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
def rows(name):
    with (DATA/name).open() as f:return list(csv.DictReader(f))
r=rows('runs.csv');keys=[tuple(x[k] for k in ['agent','condition','trial','task']) for x in r]
assert len(r)==600 and len(set(keys))==600
assert sum(x['xlsx_false_negative']=='True' for x in r)==59
assert sum(x['timeout']=='True' for x in r)==60
assert sum(x['timeout']=='True' and float(x['reward'])==1 for x in r)==17
b=json.loads((DATA/'billing_coverage.json').read_text())
assert b['generation_records']==4732 and b['unresolved_lookups']==0
assert b['models']=={'deepseek/deepseek-v4-pro-20260423':4732}
p={x['agent']:x for x in rows('provider_totals.csv')}
for a in ['pi','opencode','openhands']:
    for k in ['input','output','cached']:
        assert sum(int(float(x[k])) for x in r if x['agent']==a)==int(p[a][k])
assert float(p['openhands']['charge_usd'])<float(p['pi']['charge_usd'])<float(p['opencode']['charge_usd'])
report={}
for f in ROOT.glob('*.md'):
    source=f.read_text()
    for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',source):
        if not link.startswith(('https://','http://','#')):
            assert (f.parent/link.split('#')[0]).exists(),(f.name,link)
    prose=re.sub(r'```.*?```','',source,flags=re.S)
    prose=re.sub(r'!?\[([^\]]*)\]\([^)]+\)',r'\1',prose)
    counts=[];paragraphs=[]
    for paragraph in prose.split('\n\n'):
        if paragraph.startswith(('#','|','Source','Reference','Report date','Requirements','- ')):continue
        sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“])',paragraph)
        paragraphs.append(len(sentences))
        for sentence in sentences:counts.append(len(sentence.split()))
    assert max(counts)<=25,(f.name,max(counts))
    assert max(paragraphs)<=6,(f.name,max(paragraphs))
    assert ';' not in prose,f.name
    report[f.name]={'max_sentence_words':max(counts),'max_paragraph_sentences':max(paragraphs),
                    'sha256':hashlib.sha256(source.encode()).hexdigest()}
result={'scored_runs':600,'unique_cells':600,'provider_ids':4732,'model_ids':1,'unresolved_lookups':0,
        'token_reconciliation':'exact for all three DeepSeek harness totals',
        'false_zeros':59,'timeouts':60,'full_passes_after_timeout':17,'local_links':'all exist',
        'language_check':'sentence and paragraph limits only; not a full dictionary check',
        'reports':report}
(DATA/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
