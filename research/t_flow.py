"""사전 지정: 외국인·기관 수급 요인 (양철원 2014; 외국인 순매수의 정보력).
월간: FRGN20/FRGN60 = 최근 20/60거래일 외국인 순매수금액 합 / 시총, INST20, HOLD60 = 외국인 보유율 60일 변화.
주간(양철원식 단기): 매주 금요일 최근 5일 외국인 순매수/시총 상위 20% − 하위 20%의 다음 5일 수익률.
결합 1개: 메인(GH+SUE+자사주+국면)에 FRGN20을 1/4 비중."""
import pickle, json, glob, os, pandas as pd, numpy as np
from harness import evaluate, zr, nwt
R='/home/claude'
mc=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','Marcap','ChangesRatio']) for y in range(2019,2027)])
mc['Date']=pd.to_datetime(mc.Date)
cap=mc.pivot_table(index='Date',columns='Code',values='Marcap'); ret=mc.pivot_table(index='Date',columns='Code',values='ChangesRatio')/100
fv={};iv={};hd={}
for f in glob.glob(f'{R}/mvp-data/data/flow/*.json'):
    c=os.path.basename(f)[:-5]; d=json.load(open(f)); X=pd.DataFrame(d['rows'],columns=d['cols'])
    X['d']=pd.to_datetime(X.d); X=X.set_index('d').sort_index(); X=X[~X.index.duplicated()]
    fv[c]=X.frgn*X.close; iv[c]=X.inst*X.close; hd[c]=X.frgnHold
FV=pd.DataFrame(fv).reindex(cap.index); IV=pd.DataFrame(iv).reindex(cap.index); HD=pd.DataFrame(hd).reindex(cap.index)
def roll(X,n): return X.rolling(n,min_periods=int(n*.8)).sum()
F20=roll(FV,20)/cap; F60=roll(FV,60)/cap; I20=roll(IV,20)/cap; H60=HD-HD.shift(60)
P=pickle.load(open('panel_full.pkl','rb')); P2={}
for t,(F,fwd) in P.items():
    i=cap.index.get_indexer([pd.Timestamp(t)],method='pad')[0]; F=F.copy()
    for nm,X in (('FRGN20',F20),('FRGN60',F60),('INST20',I20),('HOLD60',H60)): F[nm]=X.iloc[i].reindex(F.index)
    P2[t]=(F,fwd)
pickle.dump(P2,open('panel_full.pkl','wb'))
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
for c in ('FRGN20','FRGN60','INST20','HOLD60'): evaluate(P2,lambda F,t,c=c: num(F,c),name=c)
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open(f'{R}/mvp-data/data/ecos.json'))['kospi']})
m=k.resample('ME').last(); ma=m.rolling(10).mean(); bear=lambda t: bool(m.asof(pd.Timestamp(t))<ma.asof(pd.Timestamp(t)))
S=lambda F: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0)+zr(num(F,'EV_BUYBACK').fillna(0)))/3
M=lambda F,t: (S(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else S(F)
evaluate(P2,M,name='메인')
evaluate(P2,lambda F,t: 0.75*M(F,t)+0.25*zr(num(F,'FRGN20')).fillna(0),name='메인+외국인20일 1/4')
# 주간 단기 검정 (유니버스: 그 달 패널 종목)
uni={pd.Timestamp(t):list(F.index) for t,(F,_) in P.items()}; ut=sorted(uni)
F5=roll(FV,5)/cap; fr=[]
fri=[d for d in cap.index if d.weekday()==4 and d>=pd.Timestamp('2020-01-01')]
for d in fri:
    u=uni[max([x for x in ut if x<=d])] if any(x<=d for x in ut) else None
    if not u: continue
    i=cap.index.get_loc(d)
    if i+5>=len(cap.index): break
    s=F5.iloc[i].reindex(u).dropna()
    if len(s)<50: continue
    nx=(1+ret.iloc[i+1:i+6][s.index]).prod()-1
    q=pd.qcut(s.rank(method='first'),5,labels=False)
    fr.append({'d':d,'hl':nx[q==4].mean()-nx[q==0].mean(),'top':nx[q==4].mean()-nx.mean()})
W=pd.DataFrame(fr)
print(f"주간 외국인5일 상위-하위 다음주 {W.hl.mean()*100:+.2f}%/주 (NW t {nwt(W.hl.values):+.1f}), 상위-평균 {W.top.mean()*100:+.2f}% (t {nwt(W.top.values):+.1f}), n={len(W)}")
for a,b in (('2020','2021'),('2022','2023'),('2024','2026')):
    g=W[(W.d.dt.year>=int(a))&(W.d.dt.year<=int(b))]; print(f"  {a}-{b}: {g.hl.mean()*100:+.2f}%/주")
