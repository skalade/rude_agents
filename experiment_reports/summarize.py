#!/usr/bin/env python3
"""Create derived tables and figures from the saved analysis and billing records."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
DATA=OUT/'data';FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
ORDER=['codex','pi','opencode','openhands','claude']
DS=['pi','opencode','openhands']
NAMES={'codex':'Codex / Terra','pi':'Pi / DeepSeek','opencode':'OpenCode / DeepSeek','openhands':'OpenHands / DeepSeek','claude':'Claude Code / Sonnet'}
r=pd.read_csv(DATA/'runs.csv');q=pd.read_csv(DATA/'requests.csv')
# Keep successful records if an earlier lookup failed.
records={};errors={}
for line in (DATA/'provider_generations.jsonl').read_text().splitlines():
    d=json.loads(line)
    if d['status']==200:records[d['id']]=d
    else:errors[d['id']]=d
errors={k:v for k,v in errors.items() if k not in records}
g=pd.DataFrame([{**{k:d[k] for k in ['agent','condition','trial','task','request_index']},**d['metadata']} for d in records.values()])
g['native_uncached']=g.native_tokens_prompt-g.native_tokens_cached
agg={'generations':('id','size'),'charge_usd':('total_cost','sum'),'input':('native_tokens_prompt','sum'),'output':('native_tokens_completion','sum'),'cached':('native_tokens_cached','sum'),'uncached':('native_uncached','sum'),'reasoning':('native_tokens_reasoning','sum')}
g.groupby('agent').agg(**agg).to_csv(DATA/'provider_totals.csv')
g.groupby(['agent','provider_name']).agg(**agg).to_csv(DATA/'provider_mix.csv')
g.groupby(['agent','condition','trial','task']).agg(**agg).to_csv(DATA/'provider_runs.csv')
g.groupby(['agent','model']).size().to_csv(DATA/'provider_models.csv',header=['generations'])
(DATA/'provider_lookup_errors.json').write_text(json.dumps(list(errors.values()),indent=2)+'\n')
# Diagnose historical effective rates. These are fitted rates, not published prices.
rates=[]
for (agent,provider),d in g.groupby(['agent','provider_name']):
    x=d[['native_uncached','native_tokens_cached','native_tokens_completion']].to_numpy()/1e6
    coeff=np.linalg.lstsq(x,d.total_cost,rcond=None)[0]
    rates.append({'agent':agent,'provider':provider,'n':len(d),'rank':int(np.linalg.matrix_rank(x)),
                  **dict(zip(['uncached_rate','cached_rate','output_rate'],coeff)),
                  'max_residual':float(np.abs(x@coeff-d.total_cost).max())})
pd.DataFrame(rates).to_csv(DATA/'fitted_provider_rates.csv',index=False)
a=r.groupby('agent').agg(n=('reward','size'),mean_score=('reward','mean'),adjusted_score=('adjusted_reward','mean'),
                        full_passes=('reward',lambda s:int((s==1).sum())),timeouts=('timeout','sum'),agent_hours=('seconds',lambda s:s.sum()/3600),
                        estimate_usd=('cost','sum'),false_zeros=('xlsx_false_negative','sum'))
a['score_without_bike']=r[r.task!='bike-rebalance'].groupby('agent').reward.mean()
a['timeout_full_passes']=r[r.timeout].groupby('agent').reward.apply(lambda s:int((s==1).sum())).reindex(a.index,fill_value=0)
a.to_csv(DATA/'score_summary.csv')
pd.crosstab([r.agent,r.task],r.reward==1).to_csv(DATA/'task_full_passes.csv')
summary={'generation_records':len(g),'unresolved_lookups':len(errors),'captured_deepseek_requests':int(q.agent.isin(DS).sum()),
         'missing_generation_ids':json.load(open(DATA/'generations_without_id.json')),
         'models':g.model.value_counts().to_dict(),'byok':g.is_byok.value_counts().to_dict()}
(DATA/'billing_coverage.json').write_text(json.dumps(summary,indent=2)+'\n')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
def save(name):
    plt.savefig(FIG/(name+'.png'),bbox_inches='tight');plt.savefig(FIG/(name+'.svg'),bbox_inches='tight');plt.close()

b=g.groupby('agent').total_cost.sum().reindex(DS)
fig,ax=plt.subplots(figsize=(8.8,4.7));x=np.arange(3);w=.34
for offset,vals,label,color in [(-w/2,a.loc[DS,'estimate_usd'],'Benchflow estimate','#a9b5c3'),(w/2,b,'OpenRouter recorded charge','#236f8b')]:
    bars=ax.bar(x+offset,vals,w,label=label,color=color)
    ax.bar_label(bars,fmt='$%.2f',padding=4)
ax.set_xticks(x,['Pi','OpenCode','OpenHands']);ax.set_ylabel('USD across 120 scored runs');ax.set_ylim(0,9)
ax.set_title('Token estimates hide a different charge order',loc='left',weight='bold',pad=16)
ax.legend(frameon=False,loc='upper left');fig.text(.125,-.01,'Captured generations only. One failed HTTP request has no generation ID.',fontsize=9,color='#555555')
save('cost_audit')

fig,axs=plt.subplots(1,2,figsize=(11,4.5))
t=r.groupby('agent')[['uncached','cached','output']].sum().reindex(DS)/1e6
base=np.zeros(3)
for k,color,label in [('uncached','#dc9153','Uncached input'),('cached','#5599b0','Cached input'),('output','#715ca5','Output')]:
    axs[0].bar(np.arange(3),t[k],bottom=base,label=label,color=color);base+=t[k]
axs[0].set_xticks(np.arange(3),['Pi','OpenCode','OpenHands']);axs[0].set_ylabel('Million tokens');axs[0].legend(frameon=False,fontsize=9)
axs[0].set_title('Total token use',loc='left',weight='bold')
v=r.groupby('agent').first_main_input.median().reindex(DS)
bars=axs[1].bar(np.arange(3),v,color=['#236f8b','#7098aa','#b0c5cf']);axs[1].bar_label(bars,fmt='%.0f',padding=3)
axs[1].set_xticks(np.arange(3),['Pi','OpenCode','OpenHands']);axs[1].set_ylabel('Median input tokens');axs[1].set_ylim(0,16000)
axs[1].set_title('First request with tools',loc='left',weight='bold')
fig.tight_layout(w_pad=3);save('token_use')

p=pd.read_csv(DATA/'paired_effects.csv');fig,axs=plt.subplots(1,3,figsize=(12,5),sharey=True)
for ax,c in zip(axs,['important','insult','threat']):
    z=p[p.condition==c].set_index('agent').loc[ORDER]
    y=np.arange(5)
    ax.errorbar(z.delta_pp,y,xerr=np.array([z.delta_pp-z.low_pp,z.high_pp-z.delta_pp]),fmt='o',capsize=4,color='#236f8b')
    ax.axvline(0,color='#999999',ls='--',lw=1);ax.set_xlim(-32,44);ax.set_title(c.capitalize(),loc='left',weight='bold')
    ax.set_yticks(y,[NAMES[a] for a in ORDER]);ax.set_xlabel('Score change (percentage points)');ax.grid(axis='x',alpha=.15)
axs[0].invert_yaxis();fig.suptitle('Tone effects remain uncertain across ten tasks',x=.02,ha='left',weight='bold',y=1.03)
fig.text(.02,-.04,'Paired task means. 95% percentile bootstrap intervals. Exploratory comparisons. No multiple-test correction to intervals.',fontsize=9)
fig.tight_layout();save('tone_effects')

m=r.pivot_table(index='task',columns='agent',values='reward')[ORDER]*100
labels={'bike-rebalance':'Bike rebalance','dialogue-parser':'Dialogue parser','earthquake-plate-calculation':'Earthquake calculation','jax-computing-basics':'JAX basics','lake-warming-attribution':'Lake attribution','sales-pivot-analysis':'Sales pivot','software-dependency-audit':'Dependency audit','travel-planning':'Travel plan','weighted-gdp-calc':'Weighted GDP','xlsx-recover-data':'Spreadsheet recovery*'}
fig,ax=plt.subplots(figsize=(9.5,6.7));im=ax.imshow(m,vmin=0,vmax=100,cmap='YlGnBu',aspect='auto')
ax.set_xticks(range(5),[NAMES[x].replace(' / ','\n') for x in ORDER]);ax.set_yticks(range(len(m)),[labels[x] for x in m.index]);ax.tick_params(length=0)
for i in range(len(m)):
    for j in range(5):ax.text(j,i,f'{m.iloc[i,j]:.1f}',ha='center',va='center',color='white' if m.iloc[i,j]>65 else '#111111')
ax.set_title('Task choice changes the apparent leader',loc='left',weight='bold',pad=18)
fig.colorbar(im,ax=ax,label='Mean recorded score (%)',shrink=.7)
fig.text(.125,-.005,'12 runs per cell. *The spreadsheet verifier has a confirmed expected-value error.',fontsize=9)
save('task_scores')
print(a.round(5).to_string());print('\nRecorded charges\n',b.to_string());print('\nCoverage',summary)

wide=r[r.agent.isin(DS)].pivot(index=['task','condition','trial'],columns='agent',values='reward')
extra={'deepseek_agreement':{'all_full_passes':int((wide.min(axis=1)==1).sum()),'any_full_passes':int((wide.max(axis=1)==1).sum()),
                            'best_observed_mean':float(wide.max(axis=1).mean())},'pi_pairwise':{},'tone_resources':{},
       'xlsx_corrected_tone':{},'zero_scores':int((r.reward==0).sum()),'false_zeros':int(r.xlsx_false_negative.sum())}
for agent in ['opencode','openhands']:
    extra['pi_pairwise'][agent]={'wins':int((wide.pi>wide[agent]).sum()),'losses':int((wide.pi<wide[agent]).sum()),'ties':int((wide.pi==wide[agent]).sum())}
for agent in ORDER:
    s=r[r.agent==agent];means=s.groupby('condition')[['seconds','output','reward','adjusted_reward']].mean()
    extra['xlsx_corrected_tone'][agent]=((means.adjusted_reward-means.loc['baseline','adjusted_reward'])*100).to_dict()
    extra['tone_resources'][agent]={c:{v:float((means.loc[c,v]/means.loc['baseline',v]-1)*100) for v in ['seconds','output']} for c in ['important','insult','threat']}
s=r[r.agent=='pi'];bike=s[s.task=='bike-rebalance']
extra['pi_bike']={'hours':float(bike.seconds.sum()/3600),'share_of_time':float(bike.seconds.sum()/s.seconds.sum()),
                  'timeout_hours':float(s[s.timeout].seconds.sum()/3600),'timeout_share_of_time':float(s[s.timeout].seconds.sum()/s.seconds.sum())}
(DATA/'extra_findings.json').write_text(json.dumps(extra,indent=2)+'\n')
# Exact reconciliation against independent provider records.
for agent in DS:
    a0=r[r.agent==agent];b0=g[g.agent==agent]
    for col,native in [('input','native_tokens_prompt'),('output','native_tokens_completion'),('cached','native_tokens_cached')]:
        assert int(a0[col].sum())==int(b0[native].sum()),(agent,col)
assert len(g)==4732 and not errors

joined=g.merge(q[['agent','condition','trial','task','index','main']],
               left_on=['agent','condition','trial','task','request_index'],
               right_on=['agent','condition','trial','task','index'],validate='one_to_one')
joined.groupby(['agent','main']).agg(generations=('id','size'),charge_usd=('total_cost','sum')).to_csv(DATA/'charges_by_request_type.csv')
