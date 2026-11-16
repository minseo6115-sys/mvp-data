"""사전 지정 국면 규칙: KOSPI가 10개월 이동평균 아래(약세 국면, Faber 2007)이면 점수에 저변동성(IVOL)을 섞는다. 파라미터 튜닝 없음."""
import pickle, json, pandas as pd, numpy as np
from harness import evaluate, zr
P=pickle.load(open('panel_full.pkl','rb'))
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open('/home/claude/mvp-data/data/ecos.json'))['kospi']})
m=k.resample('ME').last(); ma=m.rolling(10).mean()
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
A=lambda F: (zr(num(F,'MOM')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0))/2
def bear(t): t=pd.Timestamp(t); return bool(m.asof(t)<ma.asof(t))
print('약세 국면 개월 수', sum(bear(t) for t in P), '/', len(P))
evaluate(P, lambda F,t: A(F), name='A')
evaluate(P, lambda F,t: (A(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else A(F), name='A + 약세시 IVOL 50%')
evaluate(P, lambda F,t: zr(num(F,'IVOL')).fillna(0) if bear(t) else A(F), name='A / 약세시 IVOL만')
evaluate(P, lambda F,t: (A(F)+zr(num(F,'IVOL')).fillna(0))/2, name='A+IVOL 항상')
res,D=evaluate(P, lambda F,t: (A(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else A(F), name='', verbose=False)
D['y']=D.t.str[:4]; print(D.groupby('y').apply(lambda g: pd.Series({'전략':(1+g.r).prod()-1,'EW':(1+g.ew).prod()-1})).round(3).T.to_string())
