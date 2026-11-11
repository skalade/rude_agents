#!/usr/bin/env python3
"""Fetch billing metadata only for response IDs in the scored DeepSeek runs.

Reads OPENROUTER_API_KEY from the environment. Never stores or prints the key.
No model calls are made. Successful lookups persist for safe resumption.
"""
import concurrent.futures
import json
import os
from pathlib import Path

if __package__:
    from .trace_io import open_trace, trace_exists, published_result_paths
else:
    from trace_io import open_trace, trace_exists, published_result_paths
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(__file__).resolve().parent/'data'
FIELDS=['id','model','provider_name','total_cost','native_tokens_prompt','native_tokens_completion',
        'native_tokens_reasoning','native_tokens_cached','cache_discount','generation_time','latency',
        'created_at','finish_reason','is_byok','upstream_inference_cost']
gate=threading.Lock()
last_request=0.


def fetch(item):
    global last_request
    identifier=item['id']
    for attempt in range(5):
        with gate:
            pause=max(0,.1-(time.monotonic()-last_request))
            if pause:time.sleep(pause)
            last_request=time.monotonic()
        request=urllib.request.Request('https://openrouter.ai/api/v1/generation?'+urllib.parse.urlencode({'id':identifier}),
                                      headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:d=json.load(response)['data']
            return item|{'status':200,'metadata':{k:d.get(k) for k in FIELDS}}
        except urllib.error.HTTPError as exc:
            if exc.code in [429,500,502,503,504] and attempt<4:
                time.sleep(min(30,2**attempt));continue
            return item|{'status':exc.code}
        except (OSError,ValueError,KeyError) as exc:
            if attempt<4:time.sleep(2**attempt);continue
            return item|{'status':'lookup_error','error_type':type(exc).__name__}


def main():
    if not os.environ.get('OPENROUTER_API_KEY'):raise SystemExit('OPENROUTER_API_KEY missing')
    target=DATA/'provider_generations.jsonl'
    cached={}
    if target.exists():
        for line in target.read_text().splitlines():
            row=json.loads(line)
            if row['status']==200:cached[row['id']]=row
    wanted={};missing=[]
    for agent in ['pi','opencode','openhands']:
        for path in sorted((ROOT/'jobs'/agent).rglob('result.json')):
            parts=path.relative_to(ROOT/'jobs'/agent).parts
            if parts[0] not in ['baseline','important','insult','threat'] or parts[1] not in ['t1','t2','t3']:continue
            result=json.loads(path.read_text());r=result.get('rewards');r=r.get('reward') if isinstance(r,dict) else r
            if not isinstance(r,(int,float)):continue
            trajectory=path.parent/'trajectory'/'llm_trajectory.jsonl'
            if not trace_exists(trajectory):continue
            for index,line in enumerate(open_trace(trajectory)):
                d=json.loads(line);identifier=d.get('response',{}).get('body',{}).get('id')
                if not identifier:
                    missing.append({'agent':agent,'path':str(trajectory.relative_to(ROOT)),
                                    'request_index':index,'usage':d.get('response',{}).get('body',{}).get('usage'),
                                    'status_code':d.get('response',{}).get('status_code')})
                    continue
                item={'id':identifier,'agent':agent,'condition':parts[0],'trial':int(parts[1][1:]),
                      'task':result['task_name'],'request_index':index,'path':str(trajectory.relative_to(ROOT))}
                if identifier in wanted:raise RuntimeError(f'Duplicate generation ID {identifier}')
                wanted[identifier]=item
    (DATA/'generations_without_id.json').write_text(json.dumps(missing,indent=2)+'\n')
    pending=[item for k,item in wanted.items() if k not in cached]
    print(f'{len(wanted)} generation records; {len(cached)} cached; {len(pending)} pending',flush=True)
    completed=0;errors=0
    with target.open('a') as output, concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(fetch,item) for item in pending]
        for future in concurrent.futures.as_completed(futures):
            row=future.result();output.write(json.dumps(row)+'\n');output.flush()
            completed+=1;errors+=row['status']!=200
            if completed%250==0 or completed==len(pending):print(f'{completed}/{len(pending)} fetched; {errors} errors',flush=True)


if __name__=='__main__':main()
