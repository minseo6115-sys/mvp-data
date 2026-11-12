"""종목별 외국인·기관·개인 순매수(주), 외국인 보유비율 일별 이력 — 네이버 증권 모바일 API(m.stock.naver.com/api/stock/{code}/trend).
bizdate 이전 날짜를 pageSize개씩 돌려주므로 과거로 페이지를 넘겨가며 2019-11부터 받음. 이미 받은 날짜까지만 이어 받음(증분).
저장: data/flow/{code}.json = {"cols":[날짜,외국인,기관,개인,외국인보유%,종가], "rows":[...]}  + data/flow_recent.json(앱용 최근 60일 요약)"""
import os, json, time, datetime
from common import get, save, load, universe
H = {'Referer': 'https://m.stock.naver.com/', 'Accept': 'application/json'}
START = os.environ.get('FLOW_START', '20191101')
T0 = time.time(); LIMIT = float(os.environ.get('TIME_LIMIT', '15000'))
def n(x):
    x = (x or '').replace(',', '').replace('%', '').replace('+', '')
    try: return float(x) if '.' in x else int(x)
    except ValueError: return None
codes = universe(); calls = 0; fails = 0; recent = {}
for i, c in enumerate(codes):
    if time.time() - T0 > LIMIT: print('time limit at', i); break
    p = f'data/flow/{c}.json'
    old = load(p, {'rows': []}); have = {r[0]: r for r in old['rows']}
    last = max(have) if have else START
    biz = None; stop = False
    for _ in range(40):
        u = f'https://m.stock.naver.com/api/stock/{c}/trend?pageSize=60' + (f'&bizdate={biz}' if biz else '')
        try: j = json.loads(get(u, headers=H, timeout=15, tries=2)); calls += 1
        except Exception as e: fails += 1; break
        if not isinstance(j, list) or not j: break
        for r in j:
            d = r.get('bizdate')
            if not d: continue
            if d <= last and d in have: stop = True
            if d < START: stop = True; continue
            have[d] = [d, n(r.get('foreignerPureBuyQuant')), n(r.get('organPureBuyQuant')), n(r.get('individualPureBuyQuant')),
                       n(r.get('foreignerHoldRatio')), n(r.get('closePrice'))]
        nb = min(r['bizdate'] for r in j if r.get('bizdate'))
        if stop or nb == biz: break
        biz = nb; time.sleep(0.12)
    rows = sorted(have.values())
    if rows:
        save(p, {'cols': ['d', 'frgn', 'inst', 'indiv', 'frgnHold', 'close'], 'rows': rows})
        rr = rows[-60:]
        recent[c] = {'d': [r[0] for r in rr], 'frgn': [r[1] for r in rr], 'inst': [r[2] for r in rr], 'hold': [r[4] for r in rr]}
    if i % 25 == 0: print('progress', i, c, len(rows), 'calls', calls, 'fails', fails, int(time.time() - T0), 's', flush=True)
old_recent = load('data/flow_recent.json', {}).get('flow', {})
old_recent.update(recent)
save('data/flow_recent.json', {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'source': '네이버 증권 투자자별 매매동향 (단위: 주)', 'flow': old_recent})
print('flow calls', calls, 'fails', fails, 'stocks', len(recent))
