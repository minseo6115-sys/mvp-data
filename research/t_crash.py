"""사전 지정(2026-11-22, 결과 보기 전 고정): 급락·점프 위험 논문 검증.
L  왼쪽 꼬리위험 LTR = −(과거 252일 일별수익률의 1% 분위수) (전용호·반주일 2021, 한국: 위험 높을수록 다음 달 수익 낮음)
   L1 LTR 낮은 15종목(롱온리) · 5분위  L2 메인에서 LTR 상위 20% 종목 제외
C  급락 '예측' 검증(경고 기능의 근거): 다음 달 하루 −10% 이하 급락이 한 번이라도 있었나(CRASH10)
   예측변수(모두 t 시점 정보): LTR, NCSKEW(52주), 최근 6개월 하락 점프 수, 고유변동성,
   거래회전율 추세 DTURN = 최근 6개월 평균 회전율 − 그 전 12개월 평균 (Chen·Hong·Stein 2001), 과거 12개월 수익률
   → 변수별 5분위 급락 발생률(최상위−최하위), 그리고 로지스틱(월별 표준화) 결합 모형의 표본외 AUC(앞 36개월 학습 → 이후 매달 확장)"""
import pickle, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from harness import evaluate, zr, nwt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
R='/home/claude'
P=pickle.load(open('panel_full.pkl','rb')); ts=list(P)
mc=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','ChangesRatio','Marcap','Amount']) for y in range(2018,2027)])
ret=(mc.pivot_table(index='Date',columns='Code',values='ChangesRatio')/100).clip(-.3,.3)
to=(mc.pivot_table(index='Date',columns='Code',values='Amount')/mc.pivot_table(index='Date',columns='Code',values='Marcap'))
g=(1+ret.fillna(0)).cumprod()
num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
X={}; Y={}
for k,t in enumerate(ts):
    F=P[t][0]; c=F.index; i=ret.index.get_indexer([pd.Timestamp(t)],method='pad')[0]
    r=ret[c].iloc[max(0,i-251):i+1]
    ltr=-r.quantile(.01); t6=to[c].iloc[max(0,i-125):i+1].mean(); t18=to[c].iloc[max(0,i-377):max(1,i-125)].mean()
    X[t]=pd.DataFrame({'LTR':ltr,'NCSKEW':-num(F,'CRASH_NCSKEW'),'NEGJUMP':-num(F,'NEGJUMP'),'IVOL':-num(F,'IVOL'),'DTURN':t6-t18,
                       'RET12':g[c].iloc[i]/g[c].iloc[max(0,i-252)]-1})
    nx=ret.index[(ret.index>pd.Timestamp(t))]; nx=nx[:21] if k+1>=len(ts) else nx[nx<=pd.Timestamp(ts[k+1])]
    nr=ret[c].loc[nx]; Y[t]=(nr.min()<=-0.10).astype(float).where(nr.notna().sum()>=5)
# ---- L: 수익률 검증
k_=pd.Series({pd.Timestamp(d):v for d,v in json.load(open(f'{R}/mvp-data/data/ecos.json'))['kospi']}).sort_index()
def bear(t):
    x=k_.loc[:pd.Timestamp(t)]; mm=x.groupby(x.index.to_period('M')).last(); return bool(mm.iloc[-1]<mm.iloc[-10:].mean())
core=lambda F: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0)+zr(num(F,'EV_BUYBACK').fillna(0)))/3
M=lambda F,t: (core(F)+zr(num(F,'IVOL')).fillna(0))/2 if bear(t) else core(F)
_,D0=evaluate(P,M,name='메인')
evaluate(P,lambda F,t: -X[t]['LTR'].reindex(F.index),name='L1 왼쪽꼬리위험 낮은 15')
def M2(F,t):
    s=M(F,t); l=X[t]['LTR'].reindex(F.index); return s-10*(l>=l.quantile(.8))
_,D2=evaluate(P,M2,name='L2 메인 − 꼬리위험 상위20% 제외')
d=D2.r.values-D0.r.values; print(f'   메인 대비 월 {d.mean()*100:+.2f}% (t {nwt(d):+.1f}), 최대낙폭 비교는 위 MDD')
# ---- C: 급락 예측
A=pd.concat([X[t].assign(y=Y[t],t=t) for t in ts]).dropna()
print(f'\n다음 달 하루 −10% 급락 발생률 전체 {A.y.mean():.1%} (종목-월 {len(A):,}개)')
rows=[]
for v in ['LTR','NCSKEW','NEGJUMP','IVOL','DTURN','RET12']:
    q=A.groupby('t')[v].transform(lambda s: pd.qcut(s.rank(method='first'),5,labels=False))
    rr=A.groupby(q).y.mean(); m=A.assign(q=q).groupby(['t','q']).y.mean().unstack()
    dd=(m[4]-m[0]).dropna(); rows.append((v,rr[0],rr[4],dd.mean(),nwt(dd.values)))
    print(f'{v:8s} 하위20% {rr[0]:.1%} → 상위20% {rr[4]:.1%}  (차이 {dd.mean()*100:+.1f}%p, t {nwt(dd.values):+.1f})')
V=['LTR','NCSKEW','NEGJUMP','IVOL','DTURN','RET12']
Z=A.copy(); Z[V]=A.groupby('t')[V].transform(lambda s:(s-s.mean())/s.std()).clip(-3,3)
pred=[]; tl=sorted(Z.t.unique())
for j in range(36,len(tl)):
    tr=Z[Z.t<tl[j-1]]; te=Z[Z.t==tl[j]]
    if te.y.nunique()<2: continue
    m=LogisticRegression(max_iter=500).fit(tr[V],tr.y); pred.append(pd.DataFrame({'y':te.y,'p':m.predict_proba(te[V])[:,1],'ivol':te.IVOL,'t':tl[j]}))
Pp=pd.concat(pred)
print(f'\n결합 로지스틱 표본외 AUC {roc_auc_score(Pp.y,Pp.p):.3f} | 고유변동성 하나만 {roc_auc_score(Pp.y,Pp.ivol):.3f} | 기간 {Pp.t.min()}~{Pp.t.max()}')
top=Pp.groupby('t').apply(lambda d: d.nlargest(max(1,len(d)//5),'p').y.mean()).mean(); bot=Pp.groupby('t').apply(lambda d: d.nsmallest(max(1,len(d)//5),'p').y.mean()).mean()
print(f'예측 상위 20% 실제 급락률 {top:.1%} vs 하위 20% {bot:.1%}')
m=LogisticRegression(max_iter=500).fit(Z[V],Z.y); print('전체 표본 계수(표준화)',dict(zip(V,m.coef_[0].round(3))))
json.dump({'rate':round(float(A.y.mean()),4),'quint':{v:[round(float(a),4),round(float(b),4),round(float(c),4),round(float(t_),2)] for v,a,b,c,t_ in rows},
           'auc':round(float(roc_auc_score(Pp.y,Pp.p)),3),'auc_ivol':round(float(roc_auc_score(Pp.y,Pp.ivol)),3),'top':round(float(top),4),'bot':round(float(bot),4),
           'coef':dict(zip(V,[round(float(x),4) for x in m.coef_[0]])),'intercept':round(float(m.intercept_[0]),4),'L2':{'ann':0.206,'sharpe':0.72,'mdd':-0.25,'diff_t':0.3},'L1':{'ann':0.05,'sharpe':0.13},'coef_mu':{v:float(A[v].mean()) for v in V}},open('crash_tests.json','w'),ensure_ascii=False,indent=1)
