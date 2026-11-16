"""확정 모델 점검·내보내기. 점수 = (52주 고가 근접 + 실적 서프라이즈 + 자사주 공시) 순위z 평균, 약세 국면(KOSPI<10개월 평균)에는 저변동성(IVOL) 50%.
국면 판정은 t까지의 월말 종가만 사용(이번 달 포함). 비교 기준: 유니버스 동일가중(EW), 시총가중(CW), 공식 KOSPI."""
import pickle, json, pandas as pd, numpy as np
from harness import evaluate, zr, nwt, ann, sharpe, mdd
R='/home/claude'
P=pickle.load(open('panel_full.pkl','rb')); ts=list(P)
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open(f'{R}/mvp-data/data/ecos.json'))['kospi']}).sort_index()
def bear(t):
    x=k.loc[:pd.Timestamp(t)]; mm=x.groupby(x.index.to_period('M')).last()
    return bool(mm.iloc[-1]<mm.iloc[-10:].mean())
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
S=lambda F: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0)+zr(num(F,'EV_BUYBACK').fillna(0)))/3
M=lambda F,t: (S(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else S(F)
print('약세 개월',sum(bear(t) for t in ts),'/',len(ts))
res,D=evaluate(P,M,name='확정 모델')
mc=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','Marcap']) for y in range(2019,2027)])
cap=mc.pivot_table(index='Date',columns='Code',values='Marcap'); last=cap.index[-1]
cw=[];kp=[]
for a,b in zip(ts,ts[1:]+[str(last.date())]):
    f=P[a][1].dropna(); w=cap.loc[:a].iloc[-1].reindex(f.index); cw.append((f*w).sum()/w.sum()); kp.append(k.asof(pd.Timestamp(b))/k.asof(pd.Timestamp(a))-1)
D['cw']=cw; D['kospi']=kp; D['rm']=[str((pd.Timestamp(b)).date())[:7] for b in ts[1:]+[str(last.date())]]; D['y']=D.rm.str[:4]
for b in ('ew','cw','kospi'):
    x=D.r-D[b]; print(f"vs {b:5s}: 기준 연{ann(D[b]):+.1%} 샤프{sharpe(D[b]):.2f} MDD{mdd(D[b]):+.0%} | 초과 {x.mean()*100:+.2f}%/월 (t{nwt(x):+.1f}) 승률{(x>0).mean():.0%}")
print(f"모델: 연{ann(D.r):+.1%} 샤프{sharpe(D.r):.2f} MDD{mdd(D.r):+.0%}")
print(D.groupby('y').apply(lambda g: ((1+g[['r','ew','cw','kospi']]).prod()-1)).round(3).T.to_string())
rng=np.random.default_rng(0)
for b in ('ew','kospi'):
    ex=(D.r-D[b]).values; bs=[]
    for _ in range(5000):
        s=rng.integers(0,len(ex)-6,len(ex)//6+1); bs.append(np.concatenate([ex[i:i+6] for i in s])[:len(ex)].mean())
    print(b,'95%CI',np.percentile(bs,[2.5,97.5]).round(4),'P>0',(np.array(bs)>0).mean())
D.to_csv('final_monthly.csv',index=False)
