"""사전 지정(2026-11-22, 결과 보기 전 고정): 산업 모멘텀 (Moskowitz·Grinblatt 1999; 한국 KAIST 하헌호 2020).
산업 = DART 기업개황 KSIC 앞 2자리(현재 분류를 과거에도 사용). 산업 수익률 = 그 달 유니버스 안 같은 산업 종목의 시총가중 최근 6개월 수익률
(산업 종목 3개 미만이면 결측). 검증 2개: I1 산업 모멘텀 단독, I2 메인 + 산업 모멘텀 1/4. 같은 평가 조건."""
import pickle, json, pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from harness import evaluate, zr, nwt
R='/home/claude'
P=pickle.load(open('panel_full.pkl','rb')); ts=list(P)
ind={c:(v.get('ksic') or '')[:2] for c,v in json.load(open(f'{R}/mvp-data/data/company.json'))['company'].items()}
mc=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','ChangesRatio','Marcap']) for y in range(2019,2027)])
ret=(mc.pivot_table(index='Date',columns='Code',values='ChangesRatio')/100).clip(-.3,.3); cap=mc.pivot_table(index='Date',columns='Code',values='Marcap')
g=(1+ret.fillna(0)).cumprod()
IM={}
for t in ts:
    F=P[t][0]; i=g.index.get_indexer([pd.Timestamp(t)],method='pad')[0]; j=max(0,i-126)
    r6=(g.iloc[i]/g.iloc[j]-1).reindex(F.index); w=cap.iloc[i].reindex(F.index)
    d=pd.DataFrame({'r':r6,'w':w,'k':[ind.get(c,'') for c in F.index]}).dropna()
    d=d[d.k!='']; grp=d.groupby('k').apply(lambda x: np.average(x.r,weights=x.w) if len(x)>=3 else np.nan)
    IM[t]=pd.Series([grp.get(ind.get(c,''),np.nan) for c in F.index],index=F.index)
print('산업 수',len(set(v for v in ind.values() if v)),'| 평균 커버리지',round(np.mean([IM[t].notna().mean() for t in ts]),2))
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open(f'{R}/mvp-data/data/ecos.json'))['kospi']}).sort_index()
def bear(t):
    x=k.loc[:pd.Timestamp(t)]; mm=x.groupby(x.index.to_period('M')).last(); return bool(mm.iloc[-1]<mm.iloc[-10:].mean())
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
core=lambda F: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0)+zr(num(F,'EV_BUYBACK').fillna(0)))/3
iv=lambda F: zr(num(F,'IVOL')).fillna(0)
M=lambda F,t: (core(F)+iv(F))/2 if bear(t) else core(F)
_,D0=evaluate(P,M,name='메인',verbose=True)
evaluate(P,lambda F,t: IM[t],name='I1 산업 모멘텀(6개월) 단독')
def M2(F,t):
    s=(3*core(F)+zr(IM[t]).fillna(0))/4; return (s+iv(F))/2 if bear(t) else s
_,D2=evaluate(P,M2,name='I2 메인+산업 모멘텀 1/4')
d=D2.r.values-D0.r.values; print(f'   메인 대비 월 {d.mean()*100:+.2f}% (t {nwt(d):+.1f})')
print('--- 강건성')
for kw in ({'n':10},{'n':20},{'n':30},{'cost':0.006}):
    a,_=evaluate(P,M,verbose=False,**kw); b,_=evaluate(P,M2,verbose=False,**kw)
    print(kw, f"메인 연{a['ann']:+.1%} 샤프{a['sh']:.2f} MDD{a['mdd']:.0%} | I2 연{b['ann']:+.1%} 샤프{b['sh']:.2f} MDD{b['mdd']:.0%}")
