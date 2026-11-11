#!/usr/bin/env python3
"""Average the three fixed DeepSeek harnesses, preserving task clusters."""
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd

DATA=Path(__file__).resolve().parent/'data'
HARNESS=['pi','opencode','openhands']
TONE=['important','insult','threat']
SEED=20260810
DRAWS=200000

def holm(values):
    values=np.asarray(values);order=np.argsort(values)
    adjusted=np.maximum.accumulate(np.minimum(1,values[order]*(len(values)-np.arange(len(values)))))
    result=np.empty(len(values));result[order]=adjusted
    return result

r=pd.read_csv(DATA/'runs.csv');s=r[r.agent.isin(HARNESS)]
assert len(s)==360
assert not s.duplicated(['agent','task','trial','condition']).any()
assert (s.groupby(['task','trial','condition']).size()==3).all()
rows=[];task_rows=[];means=[]
for metric in ['reward','adjusted_reward']:
    pooled=s.groupby(['task','trial','condition'])[metric].mean().unstack('condition')
    for c,v in pooled.mean().items():means.append({'metric':metric,'condition':c,'score_percent':v*100})
    for tone in TONE:
        delta=(pooled[tone]-pooled.baseline).groupby('task').mean()
        a=delta.to_numpy();n=len(a);assert n==10
        rng=np.random.default_rng(SEED)
        boot=a[rng.integers(0,n,size=(DRAWS,n))].mean(axis=1)*100
        lo,hi=np.quantile(boot,[.025,.975])
        null=np.asarray(list(itertools.product([-1,1],repeat=n)))@a/n
        p=float(np.mean(np.abs(null)>=abs(a.mean())-1e-12))
        rows.append({'metric':metric,'condition':tone,'delta_pp':a.mean()*100,'low_pp':lo,'high_pp':hi,
                     'sign_flip_p':p,'positive_tasks':int(sum(a>1e-12)),
                     'negative_tasks':int(sum(a< -1e-12)),'zero_tasks':int(sum(abs(a)<=1e-12)),
                     'loo_min_pp':min(delta.drop(t).mean()*100 for t in delta.index),
                     'loo_max_pp':max(delta.drop(t).mean()*100 for t in delta.index)})
        task_rows.extend({'metric':metric,'condition':tone,'task':t,'delta_pp':v*100} for t,v in delta.items())
f=pd.DataFrame(rows)
for metric in ['reward','adjusted_reward']:
    idx=f.index[f.metric==metric];f.loc[idx,'holm_three_p']=holm(f.loc[idx,'sign_flip_p'])
# A wider family illustrates the effect of adding this follow-up to the original 15 tests.
prior=pd.read_csv(DATA/'paired_effects.csv').sign_flip_p.to_numpy()
idx=f.index[f.metric=='reward']
f.loc[idx,'holm_original_15_plus_pooled_3_p']=holm(np.r_[prior,f.loc[idx,'sign_flip_p'].to_numpy()])[-3:]
f.to_csv(DATA/'pooled_deepseek_effects.csv',index=False)
pd.DataFrame(task_rows).to_csv(DATA/'pooled_deepseek_task_effects.csv',index=False)
pd.DataFrame(means).to_csv(DATA/'pooled_deepseek_means.csv',index=False)
(DATA/'pooled_deepseek_method.json').write_text(json.dumps({'harnesses':HARNESS,'tasks':10,'trials':3,
    'runs_per_condition':90,'bootstrap_draws':DRAWS,'seed':SEED,
    'estimand':'Equal-weight average effect across these three fixed harnesses and ten selected tasks.',
    'clustering':'Average harnesses per task/trial. Pair tones with baseline. Average trial differences per task. Resample tasks.',
    'sign_flip':'Two-sided exact enumeration of 1024 task sign assignments. Assumes symmetry under the null.',
    'limits':['Exploratory follow-up','Fixed condition order','Different collection dates and providers',
              'Three fixed harnesses do not represent all possible harnesses','Ten selected tasks do not form a random task sample'],
    'multiplicity':'Holm over three pooled tone tests. Also show raw-score Holm over the original 15 tests plus these three.'},indent=2)+'\n')
print(f.round(6).to_string(index=False))
