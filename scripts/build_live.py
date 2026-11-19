"""매일: 앱이 한 번에 받아가는 data/app_live.json 생성.
- model: 오늘 기준 추천 점수(build_model.py 결과)
- vix: CBOE VIX 일별 종가(2023~), 실패하면 FRED VIXCLS
- dxy: 달러인덱스(ICE 공식 가중치로 직접 계산)와 원/달러, 주간(금요일) — ECB 기준환율(Frankfurter API)
- idx: 한국은행 공식 KOSPI·KOSDAQ 지수(일별), 기준금리(일별), 소비자물가(월별), KDI 경제정책불확실성(월별)
앱은 열 때 이 파일을 받아 내장 스냅샷을 최신 값으로 덮어쓴다."""
import json, datetime, csv, io, math, os
from common import get, save, load

today = datetime.date.today()
out = {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'log': {}}

# ---- VIX
vix = []
try:
    if os.environ.get('NONET'): raise RuntimeError('nonet')
    t = get('https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv', timeout=40, tries=3)
    for r in list(csv.reader(io.StringIO(t)))[1:]:
        m, d, y = r[0].split('/'); vix.append([f'{y}-{int(m):02d}-{int(d):02d}', round(float(r[4]), 2)])
    out['log']['vix'] = 'CBOE'
except Exception as e:
    try:
        t = get('https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS', timeout=40, tries=3)
        for r in list(csv.reader(io.StringIO(t)))[1:]:
            if r[1] not in ('', '.'): vix.append([r[0], round(float(r[1]), 2)])
        out['log']['vix'] = 'FRED (CBOE 실패: %s)' % type(e).__name__
    except Exception as e2:
        out['log']['vix'] = 'fail %s / %s' % (type(e).__name__, type(e2).__name__)
vix = [x for x in vix if x[0] >= '2023-01-01']
if vix: save('data/vix.json', {'updated': out['updated'], 'source': out['log']['vix'], 'vix': vix})
else: vix = (load('data/vix.json', {}) or {}).get('vix', [])
out['vix'] = vix

# ---- DXY (주간, 금요일) — ECB 기준환율(Frankfurter API, 한 번에 기간 조회), 실패하면 기존 파일 유지
W = {'EUR': -0.576, 'JPY': 0.136, 'GBP': -0.119, 'CAD': 0.091, 'SEK': 0.042, 'CHF': 0.036}
old = (load('data/dxy.json', {}) or {}).get('dxy', [])
try:
    if os.environ.get('NONET'): raise RuntimeError('nonet')
    j = json.loads(get('https://api.frankfurter.app/2023-01-01..?base=USD&symbols=EUR,JPY,GBP,CAD,SEK,CHF,KRW', timeout=40, tries=3))
    days = sorted(j['rates'].items()); wk = {}
    for ds, u in days:
        if not all(u.get(k) for k in W) or not u.get('KRW'): continue
        f = datetime.date.fromisoformat(ds); f += datetime.timedelta(days=(4 - f.weekday()) % 7)
        wk[f.isoformat()] = (ds, u)   # 그 주의 마지막 영업일 값
    rows = []
    for f, (ds, u) in sorted(wk.items()):
        dxy = 50.14348112 * math.prod((1 / u[k] if k in ('EUR', 'GBP') else u[k]) ** w for k, w in W.items())
        rows.append([f, round(dxy, 3), round(u['KRW'], 2)])
    if len(rows) > 50: old = rows
    out['log']['dxy'] = f'Frankfurter(ECB) {len(rows)}주'
except Exception as e:
    out['log']['dxy'] = f'fail {type(e).__name__}, 기존 {len(old)}주 유지'
save('data/dxy.json', {'updated': out['updated'], 'source': 'ECB 기준환율(Frankfurter API), ICE 공식 가중치로 계산', 'dxy': old})
out['dxy'] = old

# ---- 한국은행·KDI
ec = load('data/ecos.json', {}) or {}
f8 = lambda s: f'{s[:4]}-{s[4:6]}-{s[6:8]}'
out['idx'] = {
    'kospi': [[f8(a), b] for a, b in ec.get('kospi', []) if a >= '20250101'],
    'kosdaq': [[f8(a), b] for a, b in ec.get('kosdaq', []) if a >= '20250101'],
    'bok': [[f8(a), b] for a, b in ec.get('bok_rate_d', [])][-60:],
    'cpi': [[f'{a[:4]}-{a[4:6]}', b] for a, b in ec.get('cpi_kr_m', [])][-26:],
    'epu': [[f'{a[:4]}-{a[4:6]}', b] for a, b in (load('data/epu.json', {}) or {}).get('epu', [])][-24:],
}

# ---- 추천 모델
out['model'] = load('data/model.json', {})
save('data/app_live.json', out)
print('app_live', out['log'], 'model', out['model'].get('asOf'), 'vix', vix[-1:] if vix else None, 'dxy', old[-1:], {k: (len(v), v[-1] if v else None) for k, v in out['idx'].items()})
