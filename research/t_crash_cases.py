"""급락 사례 분석(2026-11-23): 실제 급락(하루 −10% 이하)이 무엇 때문이었고, 급락 확률(표본외 예측)이 그 전에 이미 높았나.
- 예측: t_crash.py와 같은 6개 변수·로지스틱, 2023.1부터 매달 그 전 자료로만 재추정(표본외). 각 월초 예측 확률의 유니버스 내 백분위.
- 원인 분류(급락일 기준 달력 4일 전~당일에 접수된 회사 자신의 최초 DART 공시):
  악재·경영 공시(횡령배임·소송·감사의견·거래정지·유상증자·CB·최대주주/대표이사 변경) > 실적 공시(잠정실적) > 기타 공시
  공시가 없으면: 그날 KOSPI −3% 이하면 '시장 전체 급락', 아니면 '공시 없는 급락'(뉴스·업황 등, 과거 뉴스는 수집 범위 밖)"""
import pickle, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
R='/home/claude'
P=pickle.load(open('panel_full.pkl','rb')); ts=list(P)
mc=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Name','Date','ChangesRatio','Marcap','Amount']) for y in range(2018,2027)])
NM=mc.drop_duplicates('Code',keep='last').set_index('Code').Name.to_dict()
ret=(mc.pivot_table(index='Date',columns='Code',values='ChangesRatio')/100).clip(-.3,.3)
to=(mc.pivot_table(index='Date',columns='Code',values='Amount')/mc.pivot_table(index='Date',columns='Code',values='Marcap'))
g=(1+ret.fillna(0)).cumprod()
k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open(f'{R}/mvp-data/data/ecos.json'))['kospi']}).sort_index(); kr=k.pct_change()
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
rows=[]
for j,t in enumerate(ts):
    F=P[t][0]; c=F.index; i=ret.index.get_indexer([pd.Timestamp(t)],method='pad')[0]
    r=ret[c].iloc[max(0,i-251):i+1]; t6=to[c].iloc[max(0,i-125):i+1].mean(); t18=to[c].iloc[max(0,i-377):max(1,i-125)].mean()
    X=pd.DataFrame({'LTR':-r.quantile(.01),'NCSKEW':-num(F,'CRASH_NCSKEW'),'NEGJUMP':-num(F,'NEGJUMP'),'IVOL':-num(F,'IVOL'),'DTURN':t6-t18,'RET12':g[c].iloc[i]/g[c].iloc[max(0,i-252)]-1})
    nx=ret.index[ret.index>pd.Timestamp(t)]; nx=nx[:21] if j+1>=len(ts) else nx[nx<=pd.Timestamp(ts[j+1])]
    nr=ret[c].loc[nx]; X['y']=(nr.min()<=-0.10).astype(float).where(nr.notna().sum()>=5)
    X['cday']=nr.idxmin(); X['cmin']=nr.min(); X['t']=t; X['code']=c; rows.append(X)
A=pd.concat(rows).dropna(subset=['LTR','NCSKEW','NEGJUMP','IVOL','DTURN','RET12','y'])
V=['LTR','NCSKEW','NEGJUMP','IVOL','DTURN','RET12']
Z=A.copy(); Z[V]=A.groupby('t')[V].transform(lambda s:(s-s.mean())/s.std()).clip(-3,3)
tl=sorted(Z.t.unique()); out=[]
for j in range(36,len(tl)):
    tr=Z[Z.t<tl[j-1]]; te=Z[Z.t==tl[j]].copy()
    m=LogisticRegression(max_iter=500).fit(tr[V],tr.y); te['p']=m.predict_proba(te[V])[:,1]; te['pct']=te.p.rank(pct=True); out.append(te)
O=pd.concat(out); print('표본외 AUC',round(roc_auc_score(O.y,O.p),3),'기간',O.t.min(),'~',O.t.max(),'급락',int(O.y.sum()),'/',len(O))
# 공시
E=json.load(open(f'{R}/mvp-data/data/dart_events_hist.json'))['events']
for cd,ev in json.load(open(f'{R}/mvp-data/data/dart_events.json'))['events'].items():
    got={e['no']:e for e in E.get(cd,[])}; [got.__setitem__(e['no'],e) for e in ev]; E[cd]=list(got.values())
BAD={'embezzle':'횡령·배임','lawsuit':'소송','audit':'감사의견','halt':'거래정지·관리','rights':'유상증자','cb':'전환사채','owner':'최대주주 변경','ceo':'대표이사 변경'}
def cause(code,day):
    d0=(day-pd.Timedelta(days=4)).strftime('%Y%m%d'); d1=day.strftime('%Y%m%d')
    ev=[e for e in E.get(code,[]) if d0<=e['d']<=d1 and not e['nm'].startswith('[') and '자회사' not in e['nm'] and '종속회사' not in e['nm']]
    b=[e for e in ev if e['k'] in BAD]
    if b: return '악재·경영 공시', BAD[b[0]['k']]+': '+b[0]['nm'][:40]
    if any(e['k']=='earn' for e in ev): return '실적 발표', [e['nm'][:40] for e in ev if e['k']=='earn'][0]
    if ev: return '기타 공시', ev[0]['nm'][:40]
    if kr.get(day,0)<=-0.03: return '시장 전체 급락', f'KOSPI {kr.get(day)*100:.1f}%'
    return '공시 없는 급락', ''
C=O[O.y==1].copy()
C[['cat','why']]=C.apply(lambda r: pd.Series(cause(r.code,r.cday)),axis=1)
C['name']=C.code.map(NM)
print('\n원인별: 건수, 그 전 달 급락확률 상위 20%였던 비율, 평균 백분위')
T=C.groupby('cat').agg(n=('y','size'),top20=('pct',lambda s:(s>=.8).mean()),pct=('pct','mean')).sort_values('n',ascending=False)
print(T.round(2).to_string()); print('전체 상위20% 비율',round((C.pct>=.8).mean(),2),'(무작위면 0.20)')
C=C.sort_values('cmin')
print('\n악재·경영 공시 급락 사례'); print(C[C.cat=='악재·경영 공시'][['cday','name','cmin','pct','why']].head(15).to_string(index=False))
print('\n가장 큰 급락 15건'); print(C[['cday','name','cmin','pct','cat','why']].head(15).to_string(index=False))
C.assign(cday=C.cday.dt.strftime('%Y-%m-%d')).to_csv('crash_cases.csv',index=False)
json.dump({'n':int(len(C)),'months':[str(O.t.min()),str(O.t.max())],'by_cause':{k:{'n':int(v.n),'top20':round(float(v.top20),3),'pct':round(float(v.pct),3)} for k,v in T.iterrows()},
  'top20_all':round(float((C.pct>=.8).mean()),3),
  'cases':[{'d':r.cday.strftime('%Y-%m-%d'),'name':r['name'],'r':round(float(r.cmin),3),'pct':round(float(r.pct),3),'cat':r['cat'],'why':r['why']} for _,r in pd.concat([C[C['cat']=='악재·경영 공시'],C.head(25)]).drop_duplicates(['code','cday']).iterrows()]},
  open('crash_cases.json','w'),ensure_ascii=False,indent=1)
