"""걷기전진(walk-forward) 머신러닝: 매달 t에 '과거 36개월 패널'만으로 학습 → t의 종목 점수 예측. 미래 데이터 미사용.
목표변수는 다음달 수익률의 횡단면 순위(0~1). 비교: 선형(릿지) vs 신경망(MLP, 교수님 ANN 논문 근거) vs 트리(GBM)."""
import pickle, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from harness import evaluate
src=sys.argv[1] if len(sys.argv)>1 else 'panel_price.pkl'
P=pickle.load(open(src,'rb'))
skip={'FRESH'}
keys=[k for k in next(iter(P.values()))[0].columns if k not in skip]
def prep(F):
    X=F[keys].apply(pd.to_numeric,errors='coerce').rank(pct=True)-0.5   # 횡단면 순위 정규화 → 이상치·스케일 영향 제거
    return X.fillna(0)
T=list(P); W=36
models={'RIDGE':lambda:Ridge(alpha=10),
        'MLP':lambda:MLPRegressor(hidden_layer_sizes=(16,8),alpha=1e-2,max_iter=300,early_stopping=True,random_state=0),
        'GBM':lambda:HistGradientBoostingRegressor(max_depth=3,learning_rate=.05,max_iter=150,min_samples_leaf=200,random_state=0)}
pred={m:{} for m in models}
for k in range(W,len(T)):
    tr=T[k-W:k]
    Xs=[];ys=[]
    for t in tr:
        F,fwd=P[t]; ok=fwd.notna(); Xs.append(prep(F[ok])); ys.append(fwd[ok].rank(pct=True)-0.5)
    X=pd.concat(Xs).values; y=pd.concat(ys).values
    F,fwd=P[T[k]]; Xt=prep(F)
    for m,f in models.items():
        md=f().fit(X,y); pred[m][T[k]]=pd.Series(md.predict(Xt.values),index=F.index)
Pt={t:P[t] for t in T[W:]}
print('평가 기간',T[W],'~',T[-1],len(Pt),'개월 (앞 36개월은 학습 전용)')
for m in models: evaluate(Pt, lambda F,t,m=m: pred[m][t], name=m)
evaluate(Pt, lambda F,t: F['MOM'], name='MOM (같은 기간)')
evaluate(Pt, lambda F,t: F['SIZE']*0+np.random.RandomState(abs(hash(t))%999).rand(len(F)), name='무작위 (기준선)')
pickle.dump(pred,open(src.replace('.pkl','_mlpred.pkl'),'wb'))
