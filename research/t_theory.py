"""수업 이론에 공정한 기회 주기 — 사전 지정 검증 3개 (2026-11-19, 결과를 보기 전에 정의를 고정)

기준(메인): 점수 = (52주 고가 + 실적 서프라이즈 + 자사주) 순위z 평균, 약세(KOSPI 월말 < 10개월 평균)면 + 저변동성 50%.

T1a 위험국면 점수로 약세 판정 교체: 앱의 위험국면 공식과 같은 risk = 1/(1+exp(-(zv+zc+zr+ze)/1.5))
     zv=(VIX−18)/8 (미국 종가라 하루 늦게), zc=(CDS−3년평균)/3년표준편차, zr=(KOSPI 20일 실현변동성−18)/10,
     ze=(EPU−100)/50 (월별, 발표 시차 때문에 전월 값). risk ≥ 0.5 이면 방어 모드.
T1b 둘 중 하나라도: 10개월선 약세 또는 risk ≥ 0.65 이면 방어 모드.
T2  환노출 × 환율 전망 요인 추가(1/4씩): 종목별 104주 주간 Jorion 회귀(시장 통제)의 환노출 β ×
     자산시장 실증모형(금리차·13주 환율 추세·13주 CDS 변화·VIX, 시점 t보다 13주 이전 자료로만 추정)의 13주 전망 부호
     × min(1, |전망|/2%). 앱의 '환율 수혜' 정의와 같다.
같은 평가 조건(시총 상위 150, 상위 15 동일가중, 왕복 0.6%). 결과와 관계없이 3개 모두 보고한다."""
import pickle, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from harness import evaluate, zr, nwt, ann, sharpe, mdd
R = '/home/claude'
P = pickle.load(open('panel_full.pkl', 'rb')); ts = list(P)
num = lambda F, c: pd.to_numeric(F[c], errors='coerce')

# ---- 거시 자료
fss = pd.read_csv(f'{R}/fss/data/indicators.csv', encoding='utf-8-sig', parse_dates=['date']).set_index('date').sort_index()
vx = pd.read_csv(f'{R}/vixrepo/data/vix-daily.csv', parse_dates=['DATE']).set_index('DATE')['CLOSE']
try:
    b = json.load(open(f'{R}/mvp3/data_full_base.json'))['vixDaily']
    vx = pd.concat([vx, pd.Series(b['v'], index=pd.to_datetime(b['d']))]); vx = vx[~vx.index.duplicated(keep='last')].sort_index()
except Exception as e: print('vix extra fail', e)
epu = pd.Series({pd.Period(f'{d[:4]}-{d[4:]}', 'M'): v for d, v in json.load(open(f'{R}/mvp-data/data/epu.json'))['epu']})
L = json.load(open(f'{R}/mvp-data/data/ecos_long.json'))
pol = lambda k: pd.Series({pd.Period(f'{d[:4]}-{d[4:]}', 'M'): v for d, v in L[k]})
pKR, pUS = pol('policy_KR'), pol('policy_US')
k = pd.Series({pd.Timestamp(d): v for d, v in json.load(open(f'{R}/mvp-data/data/ecos.json'))['kospi']}).sort_index()

def ma_bear(t):
    x = k.loc[:pd.Timestamp(t)]; mm = x.groupby(x.index.to_period('M')).last(); return bool(mm.iloc[-1] < mm.iloc[-10:].mean())
def risk(t):
    t = pd.Timestamp(t)
    v = vx.loc[:t - pd.Timedelta(days=1)].iloc[-1]
    c = fss.cds.loc[:t].dropna(); ch = c.iloc[-756:]
    kk = fss.kospi.loc[:t].dropna(); rv = np.log(kk).diff().iloc[-20:].std() * np.sqrt(252) * 100
    e = epu.loc[:t.to_period('M') - 1].iloc[-1]
    z = (v - 18) / 8 + (c.iloc[-1] - ch.mean()) / (ch.std() + 1e-9) + (rv - 18) / 10 + (e - 100) / 50
    return float(1 / (1 + np.exp(-z / 1.5)))
RK = {t: risk(t) for t in ts}; MB = {t: ma_bear(t) for t in ts}
print('약세 개월: 10개월선', sum(MB.values()), '| risk≥0.5', sum(v >= .5 for v in RK.values()), '| 10개월선 또는 risk≥0.65', sum(MB[t] or RK[t] >= .65 for t in ts), '/', len(ts))

# ---- 환율 실증모형 (주간, 금요일)
w = fss[['fx', 'cds']].resample('W-FRI').last().dropna()
w['vix'] = vx.reindex(vx.index.union(w.index)).ffill().reindex(w.index - pd.Timedelta(days=1), method='ffill').values
w['diff'] = [pKR.get(d.to_period('M') - 1, np.nan) - pUS.get(d.to_period('M') - 1, np.nan) for d in w.index]
w['f'] = np.log(w.fx); w['fwd13'] = w.f.shift(-13) - w.f; w['mom13'] = w.f - w.f.shift(13); w['dcds13'] = w.cds - w.cds.shift(13)
FXV = ['diff', 'mom13', 'dcds13', 'vix']
def fx_pred(t):
    t = pd.Timestamp(t); d = w[w.index <= t - pd.Timedelta(weeks=13)].dropna(subset=FXV + ['fwd13'])
    X = np.column_stack([np.ones(len(d))] + [d[v].values for v in FXV]); b = np.linalg.lstsq(X, d.fwd13.values, rcond=None)[0]
    row = w[w.index <= t].dropna(subset=FXV).iloc[-1]
    return float(b[0] + sum(b[i + 1] * row[v] for i, v in enumerate(FXV)))
FP = {t: fx_pred(t) for t in ts}
hit = [np.sign(FP[t]) == np.sign(w.f.asof(pd.Timestamp(t) + pd.Timedelta(weeks=13)) - w.f.asof(pd.Timestamp(t))) for t in ts[:-3]]
print(f'환율 13주 방향 적중률(표본외) {np.mean(hit):.0%} ({len(hit)}개월)')

# ---- 종목별 환노출 β (104주, 시장 통제)
mc = pd.concat([pd.read_parquet(f'{R}/financedata/marcap/data/marcap-{y}.parquet', columns=['Code', 'Date', 'ChangesRatio']) for y in range(2018, 2027)])
ret = (mc.pivot_table(index='Date', columns='Code', values='ChangesRatio') / 100).clip(-.3, .3)
gw = (1 + ret.fillna(0)).cumprod().where(ret.notna()).resample('W-FRI').last()
wr = gw.pct_change()
mk = fss.kospi.resample('W-FRI').last().pct_change().reindex(wr.index)
dfx = np.log(fss.fx.resample('W-FRI').last()).diff().reindex(wr.index)
def fx_beta(t, codes):
    i = wr.index.get_indexer([pd.Timestamp(t)], method='pad')[0]; sl = slice(max(1, i - 103), i + 1)
    m, f = mk.iloc[sl].values, dfx.iloc[sl].values; out = {}
    for c in codes:
        if c not in wr.columns: continue
        y = wr[c].iloc[sl].values; ok = ~np.isnan(y) & ~np.isnan(m) & ~np.isnan(f)
        if ok.sum() < 52: continue
        X = np.column_stack([np.ones(ok.sum()), m[ok], f[ok]]); out[c] = np.linalg.lstsq(X, y[ok], rcond=None)[0][2]
    return pd.Series(out)
FXB = {t: fx_beta(t, P[t][0].index) for t in ts}

core = lambda F: (zr(num(F, 'HI52')).fillna(0) + zr(num(F, 'SUE_OP')).fillna(0) + zr(num(F, 'EV_BUYBACK').fillna(0))) / 3
iv = lambda F: zr(num(F, 'IVOL')).fillna(0)
def model(bear_fn, extra=None):
    def f(F, t):
        s = core(F)
        if extra is not None:
            x = extra(F, t); s = (3 * s + zr(x.reindex(F.index)).fillna(0)) / 4
        return (s + iv(F)) / 2 if bear_fn(t) else s
    return f
fxsc = lambda F, t: FXB[t].clip(-3, 3) * np.sign(FP[t]) * min(1, abs(FP[t]) / .02)
runs = [('메인(10개월선)', model(lambda t: MB[t])),
        ('T1a 위험국면≥0.5', model(lambda t: RK[t] >= .5)),
        ('T1b 10개월선 또는 위험≥0.65', model(lambda t: MB[t] or RK[t] >= .65)),
        ('T2 메인+환노출×환율전망', model(lambda t: MB[t], fxsc))]
k_ret = {}
out = {}
for nm, f in runs:
    res, D = evaluate(P, f, name=nm)
    D['kospi'] = [k.asof(pd.Timestamp(b)) / k.asof(pd.Timestamp(a)) - 1 for a, b in zip(D.t, list(D.t[1:]) + [str(k.index[-1].date())])]
    x = D.r - D.kospi
    out[nm] = dict(ann=round(float(ann(D.r)), 4), sharpe=round(float(sharpe(D.r)), 3), mdd=round(float(mdd(D.r)), 4),
                   ex_ew=round(float(D.ex.mean()), 5), ex_kospi=round(float(x.mean()), 5), t_kospi=round(float(nwt(x)), 2),
                   sub={k2: round(float(res['ex_' + k2]) / 100, 5) for k2 in ('20-21', '22-23', '24-26')})
    if nm.startswith('메인'): base = D.r.values
    else:
        d = D.r.values - base; out[nm]['diff_vs_main'] = round(float(d.mean()), 5); out[nm]['diff_t'] = round(float(nwt(d)), 2)
        print(f'   └ 메인 대비 월 {d.mean() * 100:+.2f}% (t {nwt(d):+.1f})')
json.dump({'note': '사전 지정 3개 검증(수업 이론). 같은 평가 조건, 왕복 0.6%.', 'fx_hit': round(float(np.mean(hit)), 3),
           'bear_months': {'ma': int(sum(MB.values())), 'risk50': int(sum(v >= .5 for v in RK.values())), 'either': int(sum(MB[t] or RK[t] >= .65 for t in ts)), 'n': len(ts)},
           'runs': out}, open('theory_tests.json', 'w'), ensure_ascii=False, indent=1)
