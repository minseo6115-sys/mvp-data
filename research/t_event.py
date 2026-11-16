"""공시 사건연구: 시장(KOSPI 공식지수) 조정 누적초과수익률(CAR). 0일 = 공시 접수일(장 마감 후 공시를 감안해 [0,+1]을 공시 반응으로 봄).
구간 사전 지정: [-5,-1] 사전, [0,+1] 공시반응, [+2,+20] 1개월 표류, [+2,+60] 3개월 표류. t는 사건 간 표준오차(동일일 군집 보정 없음 → 보수적으로 해석)."""
import json, pandas as pd, numpy as np, glob
R='/home/claude'
df=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','ChangesRatio']) for y in range(2018,2027)])
df['Date']=pd.to_datetime(df.Date); df=df[df.Date>='2018-10-01']
ret=df.pivot_table(index='Date',columns='Code',values='ChangesRatio')/100
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open('/home/claude/mvp-data/data/ecos.json'))['kospi']}).sort_index()
mkt=k.pct_change().reindex(ret.index)
ab=ret.sub(mkt,axis=0).clip(-0.31,0.31)
E=json.load(open('/home/claude/mvp-data/data/dart_events.json'))
W={'사전[-5,-1]':(-5,-1),'반응[0,+1]':(0,1),'표류[+2,+20]':(2,20),'표류[+2,+60]':(2,60)}
idx=ab.index; rows=[]
for c,evs in E['events'].items():
    if c not in ab.columns: continue
    a=ab[c].values; seen=set()
    for e in evs:
        if 'nm' in e and '정정' in e['nm']: continue
        d=pd.Timestamp(e['d']); key=(e['k'],e['d'])
        if key in seen: continue
        seen.add(key); p=idx.searchsorted(d)
        if p<5 or p+60>=len(idx): continue
        r={'k':e['k'],'code':c,'d':e['d']}
        for w,(s,t) in W.items():
            x=a[p+s:p+t+1]; r[w]=np.nan if np.isnan(x).mean()>0.2 else np.nansum(x)
        rows.append(r)
X=pd.DataFrame(rows); lab={k:l for k,l,_ in E['rules']}
out=[]
for k,g in X.groupby('k'):
    o={'공시':lab.get(k,k),'건수':len(g)}
    for w in W:
        v=g[w].dropna(); o[w]=f"{v.mean()*100:+.1f}% ({v.mean()/v.std()*np.sqrt(len(v)):+.1f})"
    out.append(o)
T=pd.DataFrame(out).sort_values('건수',ascending=False)
print(T.to_string(index=False))
X.to_pickle('events_car.pkl')
summ={r['공시']:{**{w:r[w] for w in W},'n':int(r['건수'])} for r in out}
json.dump({'windows':list(W),'note':'KOSPI 조정 CAR, 괄호=t','table':summ},open('event_study.json','w'),ensure_ascii=False,indent=1)
