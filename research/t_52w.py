"""George-Hwang(2004) 52주 고가 근접도: 현재가 / 과거 252일 최고가. 한국: 류호영(2021) — JT 모멘텀보다 우수."""
import pickle, pandas as pd, numpy as np
from harness import evaluate, zr
R='/home/claude'
df=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','Close','Stocks']) for y in range(2018,2027)])
# 수정주가 대용: 시총/현재주식수 대신 종가를 액면분할 보정 위해 (Close*Stocks)/Stocks_t 사용
px=df.pivot_table(index='Date',columns='Code',values='Close'); st=df.pivot_table(index='Date',columns='Code',values='Stocks')
adj=px*st/st.ffill().iloc[-1]   # 단순 근사(주식수 변화 반영); 비율만 쓰므로 t시점 기준으로 다시 계산
P=pickle.load(open('panel_full.pkl','rb'))
P2={}
for t,(F,fwd) in P.items():
    ts=pd.Timestamp(t); i=px.index.get_indexer([ts],method='pad')[0]
    cap=(px*st).iloc[i-251:i+1][F.index]; sh=st.iloc[i][F.index]
    ap=cap/sh            # t시점 주식수 기준 수정주가 (증자·분할 왜곡 완화)
    F=F.copy(); F['HI52']=ap.iloc[-1]/ap.max(); P2[t]=(F,fwd)
pickle.dump(P2,open('panel_full.pkl','wb'))
num=lambda F,k: pd.to_numeric(F[k],errors='coerce')
evaluate(P2, lambda F,t: num(F,'HI52'), name='52주 고가 근접(GH)')
evaluate(P2, lambda F,t: num(F,'MOM'), name='모멘텀 12-1(JT)')
evaluate(P2, lambda F,t: (zr(num(F,'HI52')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0))/2, name='GH+실적서프라이즈')
evaluate(P2, lambda F,t: (zr(num(F,'MOM')).fillna(0)+zr(num(F,'SUE_OP')).fillna(0))/2, name='A: JT+실적서프라이즈')
