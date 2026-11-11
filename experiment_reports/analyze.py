#!/usr/bin/env python3
"""Audit 600 scored runs. Preserve the original report and raw artifacts."""
import argparse
import collections
import csv
import json
import re
from pathlib import Path

if __package__:
    from .trace_io import open_trace, trace_exists, published_result_paths
else:
    from trace_io import open_trace, trace_exists, published_result_paths

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
DATA = OUT / 'data'
AGENTS = ['codex', 'pi', 'opencode', 'openhands', 'claude']
DEEPSEEK = ['pi', 'opencode', 'openhands']
CONDITIONS = ['baseline', 'important', 'insult', 'threat']
SEED = 20260810


def dump(name, value):
    (DATA / name).write_text(json.dumps(value, indent=2, default=lambda x: x.item())+'\n')


def interval(values):
    a=np.asarray(values)
    rng=np.random.default_rng(SEED)
    boot=a[rng.integers(0,len(a),size=(20000,len(a)))].mean(axis=1)
    return np.quantile(boot,[.025,.975])*100


def main(requests_csv=None):
    DATA.mkdir(parents=True, exist_ok=True)
    runs=[]; calls=[]; unscored=[]; configs=[]; examples=[]
    saved_calls = None
    if requests_csv is not None:
        table = pd.read_csv(requests_csv)
        saved_calls = {key: group.to_dict('records') for key, group in
                       table.groupby(['agent', 'condition', 'trial', 'task'], sort=False)}
    selected = published_result_paths(ROOT)
    selected = set(selected) if selected is not None else None
    for agent in AGENTS:
        for path in sorted((ROOT/'jobs'/agent).rglob('result.json')):
            parts=path.relative_to(ROOT/'jobs').parts
            if len(parts)<4 or parts[1] not in CONDITIONS or parts[2] not in ['t1','t2','t3']:continue
            d=json.loads(path.read_text());reward=d.get('rewards')
            reward=reward.get('reward') if isinstance(reward,dict) else reward
            if not isinstance(reward,(float,int)):
                unscored.append({'agent':agent,'path':str(path.relative_to(ROOT)),
                                 'error_category':d.get('error_category'),
                                 'cost':(d.get('final_metrics') or {}).get('total_cost_usd',0)})
                continue
            if selected is not None and path not in selected:continue
            task=d.get('task_name') or path.parent.name.split('__')[0]
            row={'agent':agent,'condition':parts[1],'trial':int(parts[2][1:]),'task':task,
                 'reward':reward,'path':str(path.relative_to(ROOT)),
                 'started_at':d.get('started_at'),'finished_at':d.get('finished_at'),
                 'error_category':d.get('error_category'), 'timeout':d.get('error_category')=='timeout',
                 'tool_calls':d.get('n_tool_calls',0),'skill_invocations':d.get('n_skill_invocations',0)}
            metrics=d.get('agent_result') or {}
            for dest,src in [('input','n_input_tokens'),('output','n_output_tokens'),('cached','n_cache_read_tokens'),('cache_write','n_cache_creation_tokens'),('cost','cost_usd')]:
                row[dest]=metrics.get(src,0) or 0
            row['uncached']=row['input']-row['cached']
            row['price_source']=metrics.get('price_source');row['usage_source']=metrics.get('usage_source')
            row['seconds']=(d.get('timing') or {}).get('agent_execution',0)
            row['total_seconds']=(d.get('timing') or {}).get('total',0)
            summary=d.get('trajectory_summary') or {}
            row['failed_tools']=(summary.get('tool_call_status_counts') or {}).get('failed',0)
            row['partial_trajectory']=summary.get('partial_trajectory',False)
            verifier=path.parent/'verifier'/'test-stdout.txt'
            vt=verifier.read_text(errors='replace') if verifier.exists() else ''
            row['xlsx_false_negative']=bool(task=='xlsx-recover-data' and reward==0 and re.search(r'expected 7444\.4, got 7610\.3(?:3)?',vt) and vt.count('PASSED ::')==18 and vt.count('FAILED ::')==1)
            row['adjusted_reward']=1 if row['xlsx_false_negative'] else reward
            cp=path.parent/'config.json';config=json.loads(cp.read_text()) if cp.exists() else {}
            ae=config.get('agent_env') or {}
            configs.append({**{k:row[k] for k in ['agent','condition','trial','task']},'model':config.get('model'),
                            'reasoning_effort':config.get('reasoning_effort'),
                            'effort_env':{k:v for k,v in ae.items() if k in ['BENCHFLOW_REASONING_EFFORT','OPENCODE_CONFIG_CONTENT','CLAUDE_CODE_EFFORT_LEVEL','CODEX_CONFIG']},
                            'skill_mode':config.get('skill_mode')})
            acp=path.parent/'trajectory'/'acp_trajectory.jsonl'
            events=[json.loads(line) for line in acp.read_text(errors='replace').splitlines() if line.strip()] if acp.exists() else []
            messages='\n'.join(e.get('text','') for e in events if e.get('type')=='agent_message')
            row['visible_chars']=len(messages)
            row['safety_advice']=bool(re.search(r"harm(?:ing)? yourself|hurt(?:ing)? yourself|do(?:n't| not) harm|emergency services|crisis|your safety|move away|step away|not worth harming|do(?:n't| not) act|please (?:stay|be) safe|stay with (?:me|someone)",messages,re.I))
            row['threat_reference']=bool(re.search(r'toaster|bathtub|electrocut|harm(?:ing)? yourself|hurt(?:ing)? yourself|crisis|\b988\b|dramatic framing|🛁|🔌',messages,re.I))
            tool_names=collections.Counter(e.get('title') or e.get('name') or e.get('tool_name') or '?' for e in events if e.get('type')=='tool_call')
            row['tool_names']=json.dumps(dict(tool_names))
            if parts[1]=='threat' and row['threat_reference']:
                excerpts=[]
                for line in messages.splitlines():
                    if re.search(r'toaster|bathtub|electrocut|harm|crisis|\b988\b|🛁|🔌',line,re.I):excerpts.append(line[:600])
                examples.append({'agent':agent,'task':task,'trial':row['trial'],'reward':reward,'excerpts':excerpts,'path':row['path']})
            trajectory=path.parent/'trajectory'/'llm_trajectory.jsonl'
            local_calls=[]
            if saved_calls is not None:
                local_calls = saved_calls.get((agent, row['condition'], row['trial'], task), [])
            elif trace_exists(trajectory):
                for index,line in enumerate(open_trace(trajectory)):
                    if not line.strip():continue
                    event=json.loads(line);request=event.get('request',{}).get('body',{});response=event.get('response',{}).get('body',{})
                    usage=response.get('usage') or {};pt=usage.get('prompt_tokens_details') or {};ct=usage.get('completion_tokens_details') or {}
                    tools=request.get('tools') or [];messages=request.get('messages') or []
                    toolnames=[t.get('function',{}).get('name',t.get('name','?')) for t in tools]
                    syschars=sum(len(json.dumps(m.get('content',''),ensure_ascii=False)) for m in messages if m.get('role') in ['system','developer'])
                    main=bool(tools)
                    call={**{k:row[k] for k in ['agent','condition','trial','task']},'index':index,'main':main,
                          'model':request.get('model'),'response_model':response.get('model'),'provider':response.get('provider'),
                          'fingerprint':response.get('system_fingerprint'),'effort':request.get('reasoning_effort'),
                          'input':usage.get('prompt_tokens',0) or 0,'output':usage.get('completion_tokens',0) or 0,
                          'cached':pt.get('cached_tokens',0) or 0,'reasoning':ct.get('reasoning_tokens',0) or 0,
                          'provider_cost':usage.get('cost'),'duration_ms':event.get('duration_ms'),
                          'system_chars':syschars,'tools_chars':len(json.dumps(tools,ensure_ascii=False)),
                          'message_chars':len(json.dumps(messages,ensure_ascii=False)),'tool_count':len(tools),'tools':json.dumps(toolnames),
                          'finish_reason':','.join(str(c.get('finish_reason','')) for c in response.get('choices',[])),
                          'status_code':event.get('response',{}).get('status_code')}
                    call['uncached']=call['input']-call['cached']
                    local_calls.append(call)
            row['requests']=len(local_calls);row['main_requests']=sum(c['main'] for c in local_calls)
            for key in ['input','output','cached','reasoning']:
                row['trace_'+key]=sum(c[key] for c in local_calls)
            maincalls=[c for c in local_calls if c['main']]
            if maincalls:
                for key in ['input','system_chars','tools_chars','tool_count']:
                    row['first_main_'+key]=maincalls[0][key]
                row['first_main_tools']=maincalls[0]['tools']
            runs.append(row);calls.extend(local_calls)
    frame=pd.DataFrame(runs);request_frame=pd.DataFrame(calls)
    assert len(frame)==600,len(frame)
    assert not frame.duplicated(['agent','condition','trial','task']).any()
    assert (frame.groupby('agent').size()==120).all()
    frame.to_csv(DATA/'runs.csv',index=False);request_frame.to_csv(DATA/'requests.csv',index=False)
    dump('unscored.json',unscored);dump('config_audit.json',configs);dump('threat_excerpts.json',examples)
    numeric=['reward','adjusted_reward','input','output','cached','uncached','cost','requests','main_requests','tool_calls','failed_tools','seconds','total_seconds','trace_input','trace_output','trace_cached','trace_reasoning','visible_chars','timeout','xlsx_false_negative']
    sums=frame.groupby('agent')[numeric].sum()
    means=frame.groupby('agent')[numeric+['first_main_input','first_main_system_chars','first_main_tools_chars','first_main_tool_count']].mean()
    sums.to_csv(DATA/'agent_totals.csv');means.to_csv(DATA/'agent_means.csv')
    frame.groupby(['agent','condition'])[numeric].mean().to_csv(DATA/'condition_means.csv')
    frame.groupby(['agent','task'])[['reward','adjusted_reward','cost','seconds','timeout']].mean().to_csv(DATA/'task_means.csv')
    frame.groupby(['agent','condition','trial']).reward.mean().to_csv(DATA/'trial_means.csv')
    effects=[];sensitivity=[]
    for agent in AGENTS:
        subset=frame[frame.agent==agent];baseline=subset[subset.condition=='baseline'].set_index(['task','trial'])
        for condition in CONDITIONS[1:]:
            treatment=subset[subset.condition==condition].set_index(['task','trial'])
            delta=treatment.reward-baseline.reward
            task_delta=delta.groupby('task').mean()
            lo,hi=interval(task_delta.to_numpy())
            # Exact sign flip over ten task-level effects, as an exploratory sensitivity check.
            values=task_delta.to_numpy();null=[]
            for bits in range(1<<len(values)):
                signs=np.array([1 if bits&(1<<i) else -1 for i in range(len(values))])
                null.append(np.mean(values*signs))
            pvalue=float(np.mean(np.abs(null)>=abs(values.mean())-1e-12))
            effects.append({'agent':agent,'condition':condition,'delta_pp':delta.mean()*100,'low_pp':lo,'high_pp':hi,
                            'wins':int((delta>0).sum()),'losses':int((delta<0).sum()),'ties':int((delta==0).sum()),'sign_flip_p':pvalue})
            for task in task_delta.index:
                sensitivity.append({'agent':agent,'condition':condition,'excluded_task':task,'delta_pp':task_delta.drop(task).mean()*100})
    effects=pd.DataFrame(effects)
    order=np.argsort(effects.sign_flip_p.to_numpy());p=effects.sign_flip_p.to_numpy()[order];adjusted=np.maximum.accumulate(np.minimum(1,p*(len(p)-np.arange(len(p)))))
    effects['holm_p']=0.;effects.iloc[order,effects.columns.get_loc('holm_p')]=adjusted
    effects.to_csv(DATA/'paired_effects.csv',index=False);pd.DataFrame(sensitivity).to_csv(DATA/'leave_one_task_out.csv',index=False)
    contrasts=[]
    for agent in ['codex','opencode','openhands','claude']:
        a=frame[frame.agent=='pi'].set_index(['task','trial','condition']).reward
        b=frame[frame.agent==agent].set_index(['task','trial','condition']).reward
        task_delta=(a-b).groupby('task').mean();lo,hi=interval(task_delta.to_numpy())
        contrasts.append({'comparison':'pi - '+agent,'delta_pp':task_delta.mean()*100,'low_pp':lo,'high_pp':hi})
    dump('overall_comparisons.json',contrasts)
    accounting={}
    for agent in DEEPSEEK:
        subset=frame[frame.agent==agent]
        x=subset[['uncached','cached','output']].to_numpy()/1e6;y=subset.cost.to_numpy()
        rates=np.linalg.lstsq(x,y,rcond=None)[0];prediction=x@rates
        accounting[agent]={'fitted_usd_per_million':dict(zip(['uncached','cached','output'],rates)),
                           'maximum_residual_usd':float(np.abs(prediction-y).max()),
                           'reconciled_input':int((subset.input==subset.trace_input).sum()),
                           'reconciled_output':int((subset.output==subset.trace_output).sum()),
                           'reconciled_cached':int((subset.cached==subset.trace_cached).sum())}
    dump('cost_accounting.json',accounting)
    audit={}
    for agent in AGENTS:
        cs=request_frame[request_frame.agent==agent]
        audit[agent]={
            'requests':len(cs),'provider_cost_count':int(cs.provider_cost.notna().sum()),
            'provider_cost_sum':float(cs.provider_cost.sum()),
            'request_models':cs.model.value_counts(dropna=False).to_dict(),
            'providers':cs.provider.fillna('not recorded').value_counts().to_dict(),
            'effort_by_main':cs.groupby('main').effort.value_counts(dropna=False).to_string(),
            'first_main_tools':frame[frame.agent==agent].first_main_tools.value_counts().to_dict(),
            'first_main_input_median':float(frame[frame.agent==agent].first_main_input.median()),
            'first_main_system_chars_median':float(frame[frame.agent==agent].first_main_system_chars.median()),
            'first_main_tools_chars_median':float(frame[frame.agent==agent].first_main_tools_chars.median()),
            'reasoning_tokens':int(cs.reasoning.sum()),
            'non_tool_requests':int((~cs.main).sum()),
            'non_tool_cost_proxy':float(((cs[~cs.main].uncached*.28+cs[~cs.main].output*.42)/1e6).sum()),
            'trace_hours':float(cs.duration_ms.sum()/3.6e6),
        }
    dump('request_audit.json',audit)
    frame[frame.condition=='threat'].groupby('agent')[['safety_advice','threat_reference']].sum().to_csv(DATA/'threat_counts.csv')
    print('Wrote',len(frame),'scored runs and',len(request_frame),'captured requests to',DATA)
    print(sums[['reward','input','output','cached','uncached','cost','requests','tool_calls','seconds','timeout']].to_string())
    print(json.dumps(accounting,indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests-csv', type=Path, help='use captured per-request usage instead of full model logs')
    args = parser.parse_args()
    main(args.requests_csv)
