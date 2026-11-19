"""연구 결과를 mvp-data/research 로 내보낸다: backtest.json(월별 수익률·통계), panel.json(브라우저 재계산용 월별 요인 z·다음 달 수익률), 사건연구, 스크립트."""
import pandas as pd, numpy as np, json, shutil, os, pickle
from harness import ann, sharpe, mdd, nwt, zr
D=pd.read_csv('final_monthly.csv'); R='/home/claude/mvp-data/research'; os.makedirs(R,exist_ok=True)
st=lambda x: dict(ann=round(float(ann(x)),4),sharpe=round(float(sharpe(x)),3),mdd=round(float(mdd(x)),4),vol=round(float(x.std()*12**.5),4))
rng=np.random.default_rng(0); boot={}
for b in ('ew','kospi'):
    ex=(D.r-D[b]).values; bs=[]
    for _ in range(5000):
        s=rng.integers(0,len(ex)-6,len(ex)//6+1); bs.append(np.concatenate([ex[i:i+6] for i in s])[:len(ex)].mean())
    boot[b]={'ci95':[round(float(x),5) for x in np.percentile(bs,[2.5,97.5])],'p_pos':round(float((np.array(bs)>0).mean()),3),
             'hist':np.histogram(bs,bins=40)[0].tolist(),'range':[round(float(min(bs)),5),round(float(max(bs)),5)]}
out={'period':[D.rm.iloc[0],D.rm.iloc[-1]],'months':len(D),'n':15,'cost_roundtrip':0.006,
 'note':'매월 말 시총 상위 150(거래대금 50억 이상)에서 상위 15종목 동일가중. 리밸런싱일보다 먼저 접수된 재무·공시만 사용(회사 자신의 최초 공시). 마지막 달은 진행 중.',
 'stats':{k:st(D[c]) for k,c in (('model','r'),('ew','ew'),('cw','cw'),('kospi','kospi'))},
 'excess':{b:{'mean_m':round(float((D.r-D[b]).mean()),5),'t_nw':round(float(nwt(D.r-D[b])),2),'hit':round(float(((D.r-D[b])>0).mean()),3)} for b in ('ew','cw','kospi')},
 'boot':{**boot,'method':'6개월 블록 부트스트랩 5,000회'},
 'ic':{'mean':round(float(D.ic.mean()),4),'t_nw':round(float(nwt(D.ic)),2)},
 'quintile':[round(float(D[f'Q{i}'].mean()),5) for i in range(1,6)],'turnover':round(float(D.to.mean()),3),
 'monthly':{'m':list(D.rm),'t':list(D.t),'model':[round(x,5) for x in D.r],'ew':[round(x,5) for x in D.ew],'cw':[round(x,5) for x in D.cw],'kospi':[round(x,5) for x in D.kospi],'ic':[round(x,4) for x in D.ic]},
 'trials':{'combined_models_tested':15,'post_hoc':'자사주 요인은 단독 검증 결과를 본 뒤 추가(사후 선택)'}}
json.dump(out,open(f'{R}/backtest.json','w'),ensure_ascii=False,separators=(',',':'))
# 브라우저 재계산용 패널: 월별 종목 코드, 요인 z(HI52·SUE·BB·IVOL), 다음 달 수익률, 시총 비중, 약세 여부
P=pickle.load(open('panel_full.pkl','rb')); k=pd.Series({pd.Timestamp(d):v for d,v in json.load(open('/home/claude/mvp-data/data/ecos.json'))['kospi']}).sort_index()
def bear(t):
    x=k.loc[:pd.Timestamp(t)]; mm=x.groupby(x.index.to_period('M')).last(); return bool(mm.iloc[-1]<mm.iloc[-10:].mean())
mc=pd.concat([pd.read_parquet(f'/home/claude/financedata/marcap/data/marcap-{y}.parquet',columns=['Code','Date','Marcap']) for y in range(2019,2027)])
cap=mc.pivot_table(index='Date',columns='Code',values='Marcap'); num=lambda F,c: pd.to_numeric(F[c],errors='coerce')
rows=[]
for i,(t,(F,fwd)) in enumerate(P.items()):
    ok=fwd.reindex(F.index).notna(); idx=F.index[ok]
    Z={'h':zr(num(F,'HI52')).fillna(0),'s':zr(num(F,'SUE_OP')).fillna(0),'b':zr(num(F,'EV_BUYBACK').fillna(0)),'v':zr(num(F,'IVOL')).fillna(0)}
    w=cap.loc[:t].iloc[-1].reindex(idx); w=w/w.sum()
    rows.append({'t':t,'bear':bear(t),'kospi':round(float(D.kospi.iloc[i]),5),'c':list(idx),**{kk:[round(float(x),4) for x in Z[kk][idx]] for kk in Z},
                 'f':[round(float(x),4) for x in fwd[idx]],'w':[round(float(x),4) for x in w]})
json.dump({'note':'t=종목 선정일(월말). h=52주 고가, s=실적 서프라이즈, b=자사주, v=저변동성의 순위 z. f=다음 달 수익률, w=시총 비중','months':rows},open(f'{R}/panel.json','w'),ensure_ascii=False,separators=(',',':'))
pass
for f in ['harness.py','factors.py','fund.py','t_52w.py','t_flow.py','t_final.py','t_event.py','t_evfac.py','t_evcombo.py','t_regime.py','t_robust.py','ml.py','fx_paper.py','export_research.py']: shutil.copy(f,f'{R}/{f}')
print(out['stats']['model'],out['excess'],{b:(boot[b]['ci95'],boot[b]['p_pos']) for b in boot}, os.path.getsize(f'{R}/panel.json')//1024,'KB')
