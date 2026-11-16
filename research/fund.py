"""기말 모델 연구 2단계: 재무(DART, 접수일 기준 시점정보)·공시 이벤트·주식수 변화 요인을 가격 패널에 붙인다.
미래정보 차단: 리밸런싱일 t에는 접수일(rc) < t 인 보고서·공시만 사용(당일 접수분 제외)."""
import json, pickle, numpy as np, pandas as pd, os
R='/home/claude'; MD=f'{R}/mvp-data/data'
P=pickle.load(open('panel_price.pkl','rb'))
fin=json.load(open(f'{MD}/fin.json'))['fin']
ev=json.load(open(f'{MD}/dart_events_hist.json'))['events']   # 전체 이력(백필 전용 파일)
mc=pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','Marcap','Stocks']) for y in range(2018,2027)])
cap=mc.pivot_table(index='Date',columns='Code',values='Marcap'); sh=mc.pivot_table(index='Date',columns='Code',values='Stocks')
ORD={'Q1':1,'H1':2,'Q3':3,'FY':4}
def table(c):
    rows=fin.get(c,[])
    if not rows: return None
    d=pd.DataFrame(rows)
    if 'NI' not in d: d['NI']=np.nan
    d['NI']=d['NI'].fillna(d.get('EBT'))   # 순이익 미수집 시 세전이익으로 대체
    for k in ('A','L','E','S','OP','NI','EBT'):
        d[k]=pd.to_numeric(d[k],errors='coerce') if k in d else np.nan
    d['y']=d.p.str[:4].astype(int); d['q']=d.p.str[4:].map(ORD); d['rc']=pd.to_datetime(d.rc,format='%Y%m%d',errors='coerce')
    return d.sort_values(['y','q'])
T={c:table(c) for c in fin}
def ttm(d,row,k):
    """누적 손익 → 최근 4분기 합: FY(y-1) + YTD(y) − YTD(y-1)"""
    if row.q==4: return row.get(k)
    fy=d[(d.y==row.y-1)&(d.q==4)]; prev=d[(d.y==row.y-1)&(d.q==row.q)]
    if fy.empty or prev.empty: return np.nan
    a,b,c_=fy.iloc[0].get(k),prev.iloc[0].get(k),row.get(k)
    return a+c_-b if pd.notna(a) and pd.notna(b) and pd.notna(c_) else np.nan
def qval(d,row,k):
    """해당 분기 단독 값(누적 차분)"""
    if row.q==1: return row.get(k)
    pr=d[(d.y==row.y)&(d.q==row.q-1)]
    return row.get(k)-pr.iloc[0].get(k) if not pr.empty and pd.notna(row.get(k)) and pd.notna(pr.iloc[0].get(k)) else np.nan
def ffacs(c,t):
    d=T.get(c)
    if d is None: return {}
    a=d[d.rc<t]   # 엄격: 리밸런싱 당일 접수분은 장 마감 후 공시일 수 있어 제외
    if a.empty: return {}
    row=a.iloc[-1]
    if (t-row.rc).days>200: return {}
    capt=cap[c].asof(t) if c in cap else np.nan
    o={}
    E=row.get('E'); A=row.get('A'); E=E if pd.notna(E) else None; A=A if pd.notna(A) and A>0 else None
    ni=ttm(a,row,'NI'); op=ttm(a,row,'OP'); s=ttm(a,row,'S')
    o['BM']=E/capt if E and E>0 else np.nan
    o['EP']=ni/capt; o['SP']=s/capt
    o['ROE']=ni/E if E and E>0 else np.nan
    o['OPA']=op/A if A else np.nan                 # 영업이익/총자산 (Novy-Marx 수익성 대용)
    o['LEV']=-(row.get('L')/A) if A and pd.notna(row.get('L')) else np.nan     # 부채비율 낮을수록 +
    ly=a[(a.y==row.y-1)&(a.q==row.q)]
    if not ly.empty:
        l=ly.iloc[0]; o['AG']=-(A/l.get('A')-1) if A and pd.notna(l.get('A')) and l.get('A')>0 else np.nan   # 자산성장 낮을수록 + (Cooper-Gulen-Schill 2008)
        q0=qval(a,row,'OP'); q1=qval(a,l,'OP')
        o['SUE_OP']=(q0-q1)/capt if pd.notna(q0) and pd.notna(q1) else np.nan  # 분기 영업이익 전년동기대비 변화/시총 (계절 랜덤워크 서프라이즈)
        n0=qval(a,row,'NI'); n1=qval(a,l,'NI')
        o['SUE_NI']=(n0-n1)/capt if pd.notna(n0) and pd.notna(n1) else np.nan
    o['FRESH']=(t-row.rc).days   # 진단용
    return o
def efacs(c,t):
    e=ev.get(c,[]); o={}
    if not e: return {k:0 for k in ('EV_ISSUE','EV_BAD','EV_BUYBACK','EV_CONTRACT','EV_OWNER')}
    df=pd.DataFrame(e); df=df[~df.nm.str.contains('자회사|종속회사')&~df.nm.str.startswith('[')]   # 회사 자신의 최초 공시만(자회사 공시·정정·연장 제외)
    if df.empty: return {k:0 for k in ('EV_ISSUE','EV_BAD','EV_BUYBACK','EV_CONTRACT','EV_OWNER')}
    df['d']=pd.to_datetime(df.d,format='%Y%m%d'); df=df[df.d<t]   # 엄격: 당일 공시 제외
    def cnt(keys,days): return int(((df.k.isin(keys))&(df.d>t-pd.Timedelta(days=days))).sum())
    o['EV_ISSUE']=-cnt(['rights','cb'],365)
    o['EV_BAD']=-cnt(['embezzle','audit','halt','lawsuit'],365)
    o['EV_BUYBACK']=cnt(['buyback','cancel'],180)
    o['EV_CONTRACT']=cnt(['contract'],90)
    o['EV_OWNER']=-cnt(['owner','ceo'],180)
    return o
P2={}
for t,(F,fwd) in P.items():
    ts=pd.Timestamp(t); rows={}
    i=sh.index.get_indexer([ts],method='pad')[0]
    for c in F.index:
        o=ffacs(c,ts); o.update(efacs(c,ts))
        s0=sh[c].iloc[i] if c in sh else np.nan; s1=sh[c].iloc[max(0,i-252)] if c in sh else np.nan
        o['NETISS']=-np.log(s0/s1) if s0 and s1 else np.nan   # 순주식발행 낮을수록 + (Pontiff-Woodgate 2008)
        rows[c]=o
    G=pd.DataFrame(rows).T
    P2[t]=(pd.concat([F,G],axis=1),fwd)
pickle.dump(P2,open('panel_full.pkl','wb'))
cov=pd.concat([F.notna().mean() for F,_ in P2.values()],axis=1).mean(1); print('coverage'); print(cov.round(2).to_string())
