"""사후(post-hoc) 1개: 단독 검증에서 가장 강했던 자사주(EV_BUYBACK)를 메인에 1/3 비중으로. 사후 선택임을 명시하고 시도 횟수에 포함."""
import pickle, json, pandas as pd
from harness import evaluate, zr
P=pickle.load(open('panel_full.pkl','rb'))
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open('/home/claude/mvp-data/data/ecos.json'))['kospi']})
m=k.resample('ME').last(); ma=m.rolling(10).mean()
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
bear=lambda t: bool(m.asof(pd.Timestamp(t))<ma.asof(pd.Timestamp(t)))
S=lambda F: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0)+zr(num(F,'EV_BUYBACK').fillna(0)))/3
f=lambda F,t: (S(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else S(F)
evaluate(P,f,name='GH+SUE+자사주+국면')
_,D=evaluate(P,f,verbose=False); D['y']=D.t.str[:4]
print(D.groupby('y').apply(lambda g: pd.Series({'전략':(1+g.r).prod()-1,'EW':(1+g.ew).prod()-1})).round(3).T.to_string())
print('--- 강건성: 종목 수 / 비용 2배')
for n in (10,20,30): evaluate(P,f,n=n,name=f'N={n}')
evaluate(P,f,cost=0.006,name='비용 2배')
import numpy as np
ex=D.ex.values; rng=np.random.default_rng(0); bs=[]
for _ in range(5000):
    s=rng.integers(0,len(ex)-6,len(ex)//6+1); bs.append(np.concatenate([ex[i:i+6] for i in s])[:len(ex)].mean())
print('월 초과수익 95% 블록부트스트랩 CI', np.percentile(bs,[2.5,97.5]).round(4), 'P(>0)', (np.array(bs)>0).mean())
