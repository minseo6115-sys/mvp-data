import pickle, pandas as pd, numpy as np
from harness import evaluate, zr
P=pickle.load(open('panel_full.pkl','rb'))
num=lambda F,k: pd.to_numeric(F[k],errors='coerce')
A=lambda F,t: (zr(num(F,'MOM')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0))/2
for n in (10,15,20,30): evaluate(P,A,n=n,name=f'A N={n}')
evaluate(P,A,cost=.006,name='A 비용 2배')
# 분기 리밸런싱: 3개월마다만 교체
T=list(P); Pq={}
res,D=evaluate(P,A,name='A 월간',verbose=False)
# 블록 부트스트랩: 초과수익 평균>0 확률
ex=D.ex.values; rng=np.random.default_rng(0); B=[]
for _ in range(5000):
    idx=np.concatenate([np.arange(s,s+6)%len(ex) for s in rng.integers(0,len(ex),len(ex)//6+1)])[:len(ex)]; B.append(ex[idx].mean())
B=np.array(B); print(f'부트스트랩(6개월 블록) 월 초과수익 95%CI [{np.percentile(B,2.5)*100:+.2f}, {np.percentile(B,97.5)*100:+.2f}]%, P(>0)={np.mean(B>0):.0%}')
# 연도별
D['y']=D.t.str[:4]; print(D.groupby('y').apply(lambda g: pd.Series({'전략':(1+g.r).prod()-1,'EW':(1+g.ew).prod()-1})).round(3).to_string())
