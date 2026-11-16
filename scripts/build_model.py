"""매일: 검증된 추천 모델을 '오늘' 기준으로 계산해 data/model.json 으로 저장.

모델(82개월 표본외 검증, 연구 스크립트 fr/t_final.py 와 같은 정의):
  점수 = (52주 고가 근접 + 실적 서프라이즈 + 자사주 공시) 순위 z 평균
  약세 국면(KOSPI 월말 종가 < 최근 10개월 평균, Faber 2007)에는 점수 50% + 저변동성(고유변동성 낮음) 50%
유니버스: 시가총액 상위 150, 20일 평균 거래대금 50억 이상, 최근 252일 중 200일 이상 거래.
가격: FinanceData/marcap (KRX 일별, GitHub 공개). 재무: DART(접수일 기준). 공시: DART list. 수급: 네이버.
ASOF=YYYY-MM-DD, STRICT=1 로 과거 시점을 재현할 수 있다(STRICT: 기준일 당일 접수분 제외 — 백테스트와 같은 규칙)."""
import os, io, json, datetime, math
import numpy as np, pandas as pd
from common import get, save, load

MDIR = os.environ.get('MARCAP_DIR', '')
STRICT = os.environ.get('STRICT') == '1'
N_UNI, LIQ, N_PICK = 150, 5e9, 15


def marcap(y):
    cols = ['Code', 'Name', 'Market', 'Date', 'Close', 'ChangesRatio', 'Marcap', 'Stocks', 'Amount']
    if MDIR: return pd.read_parquet(f'{MDIR}/marcap-{y}.parquet', columns=cols)
    b = get(f'https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{y}.parquet', binary=True, timeout=120)
    return pd.read_parquet(io.BytesIO(b), columns=cols)


def zr(x):
    x = x.rank(pct=True); return (x - x.mean()) / x.std()


today = datetime.date.today()
df = pd.concat([marcap(y) for y in (today.year - 1, today.year)])
df['Date'] = pd.to_datetime(df.Date)
df = df[df.Code.str.endswith('0') & df.Market.isin(['KOSPI', 'KOSDAQ', 'KOSDAQ GLOBAL'])]
if os.environ.get('ASOF'): df = df[df.Date <= os.environ['ASOF']]
t = df.Date.max()
px = df.pivot_table(index='Date', columns='Code', values='Close')
cap = df.pivot_table(index='Date', columns='Code', values='Marcap')
sh = df.pivot_table(index='Date', columns='Code', values='Stocks')
amt = df.pivot_table(index='Date', columns='Code', values='Amount')
ret = (df.pivot_table(index='Date', columns='Code', values='ChangesRatio') / 100).clip(-0.3, 0.3)
meta = df[df.Date == t].set_index('Code')

# ---- 유니버스
capt = cap.loc[t].dropna().sort_values(ascending=False)
liq = amt.iloc[-20:].mean()
uni = [c for c in capt.index[:N_UNI] if liq.get(c, 0) >= LIQ and ret[c].iloc[-252:].notna().sum() >= 200]

# ---- 국면: t까지의 KOSPI 월말 종가(이번 달 포함)와 최근 10개월 평균
ecos = load('data/ecos.json', {})
k = pd.Series({pd.Timestamp(d): v for d, v in ecos.get('kospi', [])}).sort_index().loc[:t]
mm = k.groupby(k.index.to_period('M')).last()
ma10 = mm.rolling(10).mean()
bear = bool(mm.iloc[-1] < ma10.iloc[-1])
mkt = k.pct_change().reindex(ret.index)

# ---- 요인 1: 52주 고가 근접 (George-Hwang 2004). 증자·분할 왜곡을 줄이려고 시총/현재 주식수로 수정주가를 만든다
adj = (cap[uni].iloc[-252:]) / sh[uni].iloc[-1]
hi52 = adj.iloc[-1] / adj.max()
hi_date = adj.idxmax()

# ---- 요인 4(약세 국면용): 고유변동성 = 시장모형 잔차의 최근 60일 표준편차
ivol = {}
r = ret[uni].iloc[-252:]; m = mkt.iloc[-252:]
for c in uni:
    y = r[c].values; ok = ~np.isnan(y) & ~np.isnan(m.values)
    if ok.sum() < 100: continue
    X = np.c_[np.ones(ok.sum()), m.values[ok]]
    b = np.linalg.lstsq(X, y[ok], rcond=None)[0]; e = y[ok] - X @ b
    ivol[c] = float(np.std(e[-60:], ddof=1))
ivol = pd.Series(ivol)

# ---- 요인 2: 실적 서프라이즈 = (이번 분기 영업이익 − 전년 같은 분기 영업이익) / 시가총액. 접수일 기준 시점정보
fin = load('data/fin.json', {}).get('fin', {})
ORD = {'Q1': 1, 'H1': 2, 'Q3': 3, 'FY': 4}; QN = {1: '1분기', 2: '2분기', 3: '3분기', 4: '4분기'}


def known(d):  # d: Timestamp
    return d < t if STRICT else d <= pd.Timestamp(today)


def qval(d, row, key):
    if row.q == 1: return row.get(key)
    pr = d[(d.y == row.y) & (d.q == row.q - 1)]
    if pr.empty or pd.isna(row.get(key)) or pd.isna(pr.iloc[0].get(key)): return np.nan
    return row.get(key) - pr.iloc[0].get(key)


sue = {}; sue_info = {}
for c in uni:
    rows = fin.get(c)
    if not rows: continue
    d = pd.DataFrame(rows)
    d['OP'] = pd.to_numeric(d['OP'], errors='coerce') if 'OP' in d else np.nan
    d['y'] = d.p.str[:4].astype(int); d['q'] = d.p.str[4:].map(ORD)
    d['rc'] = pd.to_datetime(d.rc, format='%Y%m%d', errors='coerce'); d = d.sort_values(['y', 'q'])
    a = d[d.rc.map(known)]
    if a.empty: continue
    row = a.iloc[-1]
    if (t - row.rc).days > 200: continue
    ly = a[(a.y == row.y - 1) & (a.q == row.q)]
    if ly.empty: continue
    q0 = qval(a, row, 'OP'); q1 = qval(a, ly.iloc[0], 'OP')
    if pd.isna(q0) or pd.isna(q1): continue
    sue[c] = (q0 - q1) / capt[c]
    sue_info[c] = {'p': f'{row.y}년 {QN[row.q]}', 'rc': row.rc.strftime('%Y-%m-%d'), 'q0': float(q0), 'q1': float(q1)}
sue = pd.Series(sue, dtype=float)

# ---- 요인 3: 자사주 취득·소각 공시 건수(최근 180일) + 위험·호재 공시 목록
hist = load('data/dart_events_hist.json', {}).get('events', {})
rec = load('data/dart_events.json', {}).get('events', {})
RULE = {r[0]: (r[1], r[2]) for r in (load('data/dart_events.json', {}).get('rules') or [])}
bb = {}; evs = {}
for c in uni:
    got = {e['no']: e for e in hist.get(c, [])}
    for e in rec.get(c, []): got[e['no']] = e
    L = [e for e in got.values() if known(pd.Timestamp(e['d']))]
    for e in L: e['sub'] = ('자회사' in e['nm']) or ('종속회사' in e['nm']); e['amend'] = e['nm'].startswith('[')
    own = [e for e in L if not e['sub'] and not e['amend']]   # 회사 자신의 최초 공시만 점수·경고에 사용(자회사 공시·정정·연장 제외)
    d180 = (t - pd.Timedelta(days=180)).strftime('%Y%m%d'); d365 = (t - pd.Timedelta(days=365)).strftime('%Y%m%d')
    bbs = [e for e in own if e['k'] in ('buyback', 'cancel') and e['d'] > d180]
    bb[c] = len(bbs)
    evs[c] = [{'d': e['d'], 'k': e['k'], 'nm': e['nm'], 'no': e['no']} for e in sorted(own, key=lambda e: e['d'], reverse=True)
              if e['d'] > d365 and e['k'] != 'earn'][:12]
bb = pd.Series(bb, dtype=float)

# ---- 점수
F = pd.DataFrame({'HI52': hi52, 'SUE': sue, 'BB': bb, 'IVOL': -ivol}).reindex(uni)
Z = pd.DataFrame({'HI52': zr(F.HI52).fillna(0), 'SUE': zr(F.SUE).fillna(0), 'BB': zr(F.BB.fillna(0)), 'IVOL': zr(F.IVOL).fillna(0)})
core = (Z.HI52 + Z.SUE + Z.BB) / 3
score = (core + Z.IVOL) / 2 if bear else core
rank = score.rank(ascending=False, method='first').astype(int)

# ---- 참고 정보: 수급(점수에는 넣지 않음 — 검증에서 효과 없음), 뉴스 리스크
news = load('data/news_risk.json', {}).get('news', {})
flow = {}
for c in uni:
    f = load(f'data/flow/{c}.json')
    if not f: continue
    X = pd.DataFrame(f['rows'], columns=f['cols']).tail(20)
    if len(X) < 15 or not capt.get(c): continue
    flow[c] = {'frgn20': float((X.frgn * X.close).sum() / capt[c]), 'inst20': float((X.inst * X.close).sum() / capt[c]),
               'hold': float(X.frgnHold.iloc[-1]), 'd': str(X.d.iloc[-1])}


def rnd(x, n=4):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)


stocks = []
for c in sorted(uni, key=lambda c: rank[c]):
    stocks.append({
        'code': c, 'name': meta.Name.get(c), 'market': meta.Market.get(c), 'rank': int(rank[c]), 'score': rnd(score[c], 3),
        'close': rnd(px[c].iloc[-1], 0), 'mcap': rnd(capt[c] / 1e8, 0),
        'z': {k2: rnd(Z[k2][c], 4) for k2 in Z},
        'hi52': rnd(F.HI52[c]), 'hiDate': hi_date[c].strftime('%Y-%m-%d') if c in hi_date and pd.notna(hi_date[c]) else None,
        'sue': rnd(F.SUE[c], 5), 'sueInfo': sue_info.get(c), 'bb': int(F.BB.fillna(0)[c]), 'ivol': rnd(ivol.get(c), 5),
        'events': evs.get(c, []), 'news': (news.get(c) or {}).get('hits', [])[:6], 'flow': flow.get(c),
    })

out = {
    'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'asOf': t.strftime('%Y-%m-%d'), 'strict': STRICT,
    'model': {'name': '52주 고가 + 실적 서프라이즈 + 자사주 + 약세장 규칙', 'nPick': N_PICK,
              'weights': ({'HI52': 1 / 6, 'SUE': 1 / 6, 'BB': 1 / 6, 'IVOL': 1 / 2} if bear else {'HI52': 1 / 3, 'SUE': 1 / 3, 'BB': 1 / 3, 'IVOL': 0})},
    'regime': {'bear': bear, 'kospi': rnd(mm.iloc[-1], 2), 'ma10': rnd(ma10.iloc[-1], 2),
               'hist': [[str(p), rnd(v, 2), rnd(a, 2)] for p, v, a in zip(mm.index[-36:], mm.values[-36:], ma10.values[-36:])]},
    'universe': {'n': len(uni), 'rule': f'시가총액 상위 {N_UNI} · 20일 평균 거래대금 50억원 이상 · 최근 252일 중 200일 이상 거래'},
    'coverage': {'sue': int(F.SUE.notna().sum()), 'bb': int((F.BB > 0).sum()), 'flow': len(flow)},
    'rules': RULE, 'stocks': stocks,
}
save(os.environ.get('OUT', 'data/model.json'), out)
print('model', out['asOf'], 'bear', bear, 'n', len(uni), 'cov', out['coverage'], 'top', [s['name'] for s in stocks[:15]])

# ---- 수집 대상(universe.json)에 새로 상위 150에 든 종목을 추가 → 다음 수집부터 재무·공시·수급을 받음
if not os.environ.get('ASOF'):
    U = load('universe.json')
    have = {s['code'] for s in U['codes']}
    new = [c for c in capt.index[:N_UNI] if c not in have]
    if new:
        U['codes'] += [{'code': c, 'name': meta.Name.get(c)} for c in new]; U['n'] = len(U['codes'])
        json.dump(U, open('universe.json', 'w'), ensure_ascii=False, separators=(',', ':'))
        print('universe +', len(new), [meta.Name.get(c) for c in new])
