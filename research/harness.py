"""공통 평가 도구: 점수 → (순위IC, 상위N 동일가중 롱온리의 EW 대비 초과수익·t값, 5분위, 하위기간, 회전율).
'IC가 좋아도 실제로 사면 못 이길 수 있다'는 문제 때문에 롱온리 초과수익을 주 기준으로 쓴다."""
import numpy as np, pandas as pd
PER={'20-21':('2019-12','2021-12'),'22-23':('2022-01','2023-12'),'24-26':('2024-01','2026-12')}
def zr(x): x=x.rank(pct=True); return (x-x.mean())/x.std()
def nwt(x,L=3):
    x=np.asarray(x,float); x=x[~np.isnan(x)]; n=len(x); m=x.mean(); c=x-m
    g=[(c[k:]*c[:n-k]).sum()/n for k in range(L+1)]; v=g[0]+2*sum((1-k/(L+1))*g[k] for k in range(1,L+1))
    return m/np.sqrt(v/n) if v>0 else np.nan
def ann(r): r=pd.Series(r); return (1+r).prod()**(12/len(r))-1
def sharpe(r,rf=.028): r=pd.Series(r); return (ann(r)-rf)/(r.std()*np.sqrt(12))
def mdd(r): e=(1+pd.Series(r)).cumprod(); return (e/e.cummax()-1).min()
def evaluate(P, score, n=15, cost=0.003, name='', verbose=True, buffer=None):
    """P: {t:(F,fwd)}; score(F,t)->Series. buffer: 보유종목은 순위 buffer 이내면 유지."""
    rows=[]; prev=[]
    for t,(F,fwd) in P.items():
        s=score(F,t); s=s[fwd.reindex(s.index).notna()].dropna()
        if len(s)<30: continue
        rk=s.rank(ascending=False)
        if buffer and prev:
            keep=[c for c in prev if c in rk and rk[c]<=buffer]
            pick=keep+[c for c in rk.sort_values().index if c not in keep][:max(0,n-len(keep))]
        else: pick=list(rk.sort_values().index[:n])
        to=1. if not prev else len(set(pick)-set(prev))/n
        f=fwd[s.index]; r=f[pick].mean()-to*cost*2
        q=pd.qcut(s.rank(method='first'),5,labels=False)+1; qm=f.groupby(q).mean()
        ew=fwd.dropna().mean()
        rows.append(dict(t=t,r=r,ew=ew,ex=r-ew,ic=s.rank().corr(f.rank()),to=to,**{f'Q{i}':qm.get(i,np.nan) for i in range(1,6)}))
        prev=pick
    D=pd.DataFrame(rows)
    res=dict(name=name,IC=D.ic.mean(),IC_t=nwt(D.ic),ex_m=D.ex.mean()*100,ex_t=nwt(D.ex),hit=(D.ex>0).mean(),
             ann=ann(D.r),ew_ann=ann(D.ew),sh=sharpe(D.r),ew_sh=sharpe(D.ew),mdd=mdd(D.r),to=D.to.mean(),
             **{f'Q{i}':D[f'Q{i}'].mean()*100 for i in range(1,6)},
             **{f'ex_{k}':D[(D.t>=a)&(D.t<=b)].ex.mean()*100 for k,(a,b) in PER.items()})
    if verbose:
        print(f"{name:26s} IC {res['IC']:+.3f}(t{res['IC_t']:+.1f}) 초과 {res['ex_m']:+.2f}%/월(t{res['ex_t']:+.1f}) 승률{res['hit']:.0%} "
              f"연{res['ann']:+.1%}/EW{res['ew_ann']:+.1%} 샤프{res['sh']:.2f}/{res['ew_sh']:.2f} MDD{res['mdd']:+.0%} 회전{res['to']:.2f} | "
              + ' '.join(f"{k}:{res['ex_'+k]:+.2f}" for k in PER) + ' | Q1..5 ' + ' '.join(f"{res[f'Q{i}']:+.1f}" for i in range(1,6)))
    return res, D
