"""사전 지정(3+5개): ① 공시 요인 단독 5개 ② 메인 후보(GH+SUE+국면)에서 악재 공시(1년 내 횡령·소송·감사·정지) 보유 종목 제외
③ 메인에서 최근 180일 대표이사·최대주주 변경 종목 제외 ④ 메인 + 공급계약(90일) 가점 0.25"""
import pickle, json, pandas as pd
from harness import evaluate, zr
P=pickle.load(open('panel_full.pkl','rb'))
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open('/home/claude/mvp-data/data/ecos.json'))['kospi']})
m=k.resample('ME').last(); ma=m.rolling(10).mean()
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
bear=lambda t: bool(m.asof(pd.Timestamp(t))<ma.asof(pd.Timestamp(t)))
G=lambda F: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0))/2
M=lambda F,t: (G(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else G(F)
for c in ['EV_ISSUE','EV_BAD','EV_BUYBACK','EV_CONTRACT','EV_OWNER']:
    evaluate(P, lambda F,t,c=c: num(F,c).fillna(0)+1e-6*zr(num(F,'HI52')).fillna(0), name=c)
evaluate(P, M, name='메인(GH+SUE+국면)')
evaluate(P, lambda F,t: M(F,t)-10*(num(F,'EV_BAD').fillna(0)<0), name='메인-악재공시 제외')
evaluate(P, lambda F,t: M(F,t)-10*(num(F,'EV_OWNER').fillna(0)<0), name='메인-경영진변경 제외')
evaluate(P, lambda F,t: M(F,t)+0.25*(num(F,'EV_CONTRACT').fillna(0)>0), name='메인+공급계약 가점')
