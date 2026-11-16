"""기말 모델 연구 1단계: 가격 기반 후보 요인의 표본외 예측력 검증 (생존편향 없는 매월 시총 상위 150, 2020.01~).
각 요인은 리밸런싱 시점 t까지의 데이터로만 계산하고, 다음 달 수익률과의 순위상관(IC)을 측정한다."""
import pandas as pd, numpy as np, json, warnings; warnings.filterwarnings('ignore')
R='/home/claude'
df=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','ChangesRatio','Close','Marcap','Amount','Market']) for y in range(2018,2027)])
df=df[df.Code.str.endswith('0')&df.Market.isin(['KOSPI','KOSDAQ','KOSDAQ GLOBAL'])]
ret=df.pivot_table(index='Date',columns='Code',values='ChangesRatio')/100
ret=ret.clip(-0.3,0.3)
mc=df.pivot_table(index='Date',columns='Code',values='Marcap')
amt=df.pivot_table(index='Date',columns='Code',values='Amount')
fss=pd.read_csv(f'{R}/fss/data/indicators.csv',encoding='utf-8-sig',parse_dates=['date']).set_index('date')
mkt=fss.kospi.pct_change().reindex(ret.index)
# 시장 수익률 결측(2018.5 이전)은 시총가중 수익률로 대체
cw=(ret*mc.shift(1)).sum(1)/mc.shift(1).where(ret.notna()).sum(1)
mkt=mkt.fillna(cw)
dates=ret.index
me=pd.Series(dates,index=dates).groupby(dates.to_period('M')).max()   # 월말 거래일
rebal=[d for d in me.values if pd.Timestamp(d)>=pd.Timestamp('2019-12-01')]
rebal=[pd.Timestamp(d) for d in rebal]
def facs(t):
    i=dates.get_loc(t)
    cap=mc.loc[t].dropna(); liq=amt.iloc[i-19:i+1].mean()
    uni=cap.sort_values(ascending=False).index[:150]
    uni=[c for c in uni if liq.get(c,0)>=5e9 and ret[c].iloc[i-251:i+1].notna().sum()>=200]
    r=ret[uni].iloc[i-251:i+1]; m=mkt.iloc[i-251:i+1]
    out={}
    lr=np.log1p(r)
    out['MOM']=lr.iloc[:-21].sum()                         # 12-1개월
    out['REV']=-lr.iloc[-21:].sum()                         # 1개월 반전
    vol=r.iloc[-60:].std(); out['LOWVOL']=-vol
    mm=m.iloc[-252:]; X=np.c_[np.ones(len(mm)),mm.values]
    B=[];RES=[]
    for c in uni:
        y=r[c].values; ok=~np.isnan(y)&~np.isnan(mm.values)
        b=np.linalg.lstsq(X[ok],y[ok],rcond=None)[0]; e=y[ok]-X[ok]@b; B.append(b[1]); RES.append(pd.Series(e,index=mm.index[ok]))
    out['LOWBETA']=-pd.Series(B,index=uni)
    res=dict(zip(uni,RES))
    out['IVOL']=-pd.Series({c:res[c].iloc[-60:].std() for c in uni})
    out['MAX']=-r.iloc[-21:].max()                          # 복권형 급등(Bali et al. 2011)
    # 주가급락위험: 주간 기업고유수익률의 음의 왜도(NCSKEW), 하락/상승 변동성비(DUVOL) (Chen-Hong-Stein 2001; Kim-Li-Zhang 2011)
    ns={};du={};jn={};jd={}
    for c in uni:
        e=res[c]; w=np.log1p(e).groupby(e.index.to_period('W')).sum(); w=w-w.mean(); n=len(w)
        if n<40: continue
        ns[c]=-(n*(n-1)**1.5*(w**3).sum())/((n-1)*(n-2)*((w**2).sum())**1.5)
        up=w[w>0];dn=w[w<0]
        du[c]=np.log(((len(up)-1)*(dn**2).sum())/((len(dn)-1)*(up**2).sum())) if len(up)>2 and len(dn)>2 else np.nan
        # 점프: 일별 고유수익률이 직전 60일 표준편차의 3배를 넘는 날 (Lee-Mykland 식 근사, Jiang-Yao 2013)
        s=e.rolling(60,min_periods=40).std().shift(1); z=(e/s).iloc[-126:]
        jn[c]=(z<-3).sum(); jd[c]=(z.abs()>3).sum()
    out['CRASH_NCSKEW']=-pd.Series(ns); out['CRASH_DUVOL']=-pd.Series(du)
    out['NEGJUMP']=-pd.Series(jn); out['JUMPS']=-pd.Series(jd)
    out['SIZE']=-np.log(cap[uni])
    am=(r.abs().iloc[-60:]/amt[uni].iloc[i-59:i+1]).mean()*1e9; out['ILLIQ']=np.log(am)   # Amihud 비유동성(높을수록 프리미엄 기대)
    F=pd.DataFrame(out).reindex(uni)
    return F
rows=[]; panel={}
for k,t in enumerate(rebal[:-1]):
    t2=rebal[k+1]; i=dates.get_loc(t); j=dates.get_loc(t2)
    F=facs(t)
    fwd=np.expm1(np.log1p(ret[F.index].iloc[i+1:j+1]).sum())
    panel[str(t.date())]=(F,fwd)
    for f in F.columns:
        x=F[f]; ok=x.notna()&fwd.notna()
        if ok.sum()<30: continue
        ic=x[ok].rank().corr(fwd[ok].rank())
        q=pd.qcut(x[ok].rank(method='first'),5,labels=False)
        rows.append(dict(t=str(t.date()),f=f,ic=ic,spread=fwd[ok][q==4].mean()-fwd[ok][q==0].mean(),n=int(ok.sum())))
    print(t.date(),len(F),flush=True) if k%12==0 else None
D=pd.DataFrame(rows)
import pickle; pickle.dump(panel,open('/home/claude/mvp2/fr/panel_price.pkl','wb')); D.to_csv('/home/claude/mvp2/fr/ic_price.csv',index=False)
def nw_t(x,L=3):
    x=np.asarray(x)-np.mean(x); n=len(x); g=[(x[k:]*x[:n-k]).sum()/n for k in range(L+1)]
    v=g[0]+2*sum((1-k/(L+1))*g[k] for k in range(1,L+1)); return np.mean(np.asarray(x)+0)/1 if v<=0 else None
out=[]
for f,g in D.groupby('f'):
    ic=g.ic.values; n=len(ic); m=ic.mean(); s=ic.std(ddof=1)
    xc=ic-m; L=3; gam=[(xc[k:]*xc[:n-k]).sum()/n for k in range(L+1)]; v=gam[0]+2*sum((1-k/(L+1))*gam[k] for k in range(1,L+1))
    t=m/np.sqrt(v/n)
    sub={p:g[(g.t>=a)&(g.t<=b)].ic.mean() for p,(a,b) in {'20-21':('2019-12','2021-12'),'22-23':('2022-01','2023-12'),'24-26':('2024-01','2026-12')}.items()}
    out.append(dict(f=f,IC=round(m,4),t_NW=round(t,2),hit=round((ic>0).mean(),2),spread_m=round(g.spread.mean()*100,2),**{k:round(v,3) for k,v in sub.items()},months=n))
T=pd.DataFrame(out).sort_values('t_NW',ascending=False); print(T.to_string(index=False)); T.to_csv('/home/claude/mvp2/fr/summary_price.csv',index=False)
