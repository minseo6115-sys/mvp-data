"""교수님 논문 재현(양오석·한재훈 2019): 원/달러 환율 — 통화론(금리·물가) 모형 vs 주식시장모형(+KOSPI·외국인 순매수), 회귀 vs 인공신경망.
(1) 동행 설명력(논문과 같은 방식, 월간 변화율 회귀 R²), (2) 1개월 앞 표본외 예측 RMSE·방향 적중률 vs 랜덤워크(Meese-Rogoff 1983), Diebold-Mariano 검정."""
import json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
d=json.load(open('/home/claude/mvp-data/data/ecos_long.json'))
S=lambda k,f='%Y%m%d': pd.Series({pd.to_datetime(a,format=f):b for a,b in d[k]})
fx=S('usdkrw').resample('ME').last(); ks=S('kospi').resample('ME').last(); fr=S('frgn_kospi').resample('ME').sum()
kt=S('ktb3y').resample('ME').mean()
pk=S('policy_KR','%Y%m').resample('ME').last(); pu=S('policy_US','%Y%m').resample('ME').last()
ck=S('cpi_KR','%Y%m').resample('ME').last(); cu=S('cpi_US','%Y%m').resample('ME').last()
D=pd.DataFrame({'dfx':np.log(fx).diff()*100,'rdiff':pk-pu,'d_rdiff':(pk-pu).diff(),'infl':(np.log(ck).diff(12)-np.log(cu).diff(12))*100,
                'kospi':np.log(ks).diff()*100,'frgn':fr/1e4,'dkt':kt.diff()}).dropna()
mono=['rdiff','d_rdiff','infl']; stock=mono+['kospi','frgn']
out={'n':len(D),'start':str(D.index[0].date()),'end':str(D.index[-1].date())}
# (1) 동행 설명력
for nm,X in (('통화론 모형',mono),('주식시장 모형',stock)):
    m=LinearRegression().fit(D[X],D.dfx); out[f'R2_{nm}']=round(m.score(D[X],D.dfx),3)
m=LinearRegression().fit(D[stock],D.dfx); out['coef_stock']=dict(zip(stock,np.round(m.coef_,3)))
# (2) 표본외 1개월 앞 예측 (설명변수는 t월, 목표는 t+1월 변화) — 60개월 확장창
Y=D.dfx.shift(-1).dropna(); X=D.loc[Y.index]
pred={k:[] for k in ('RW','통화론-회귀','주식시장-회귀','주식시장-신경망')}; act=[]
for i in range(60,len(Y)):
    tr=slice(0,i); act.append(Y.iloc[i]); pred['RW'].append(0.0)
    for nm,cols,kind in (('통화론-회귀',mono,'ols'),('주식시장-회귀',stock,'ols'),('주식시장-신경망',stock,'ann')):
        sc=StandardScaler().fit(X[cols].iloc[tr]); a=sc.transform(X[cols].iloc[tr]); b=sc.transform(X[cols].iloc[[i]])
        if kind=='ols': p=LinearRegression().fit(a,Y.iloc[tr]).predict(b)[0]
        else: p=np.mean([MLPRegressor(hidden_layer_sizes=(6,),alpha=1.0,max_iter=2000,random_state=s).fit(a,Y.iloc[tr]).predict(b)[0] for s in range(5)])
        pred[nm].append(p)
act=np.array(act); res={}
def dm(e1,e2,h=1):
    dd=e1**2-e2**2; n=len(dd); return dd.mean()/np.sqrt(dd.var(ddof=1)/n)
for k,v in pred.items():
    v=np.array(v); e=act-v
    res[k]=dict(RMSE=round(float(np.sqrt((e**2).mean())),3),방향적중=round(float(np.mean(np.sign(v)==np.sign(act))) if k!='RW' else None,3) if k!='RW' else None,
                DM_vs_RW=round(float(dm(e,act)),2) if k!='RW' else None)
out['oos']=res; out['oos_months']=len(act); out['oos_start']=str(Y.index[60].date())
print(json.dumps(out,ensure_ascii=False,indent=1,default=str))
json.dump(out,open('fx_paper.json','w'),ensure_ascii=False,default=str)
