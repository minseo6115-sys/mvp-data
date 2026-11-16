"""기업 개황(DART company.json): 업종코드(KSIC), 대표이사, 결산월, 설립일. 종목당 1회 받고 60일마다 갱신(대표이사 변경 반영)."""
import json, time, datetime
from common import get, save, load, corp_map, universe, DART
cm = corp_map(); U = universe(); today = datetime.date.today().isoformat()
old = (load('data/company.json', {}) or {}).get('company', {})
out = dict(old); calls = 0
for c in U:
    cc = cm.get(c); o = old.get(c)
    if not cc: continue
    if o and (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(o.get('at', '2000-01-01'))).days < 60: continue
    if calls >= 400: break
    try: j = json.loads(get(f'https://opendart.fss.or.kr/api/company.json?crtfc_key={DART}&corp_code={cc}', timeout=20, tries=2))
    except Exception as e: print('err', c, type(e).__name__); continue
    calls += 1
    if j.get('status') == '020': print('rate limit'); break
    if j.get('status') != '000': continue
    out[c] = {'name': j.get('stock_name') or j.get('corp_name'), 'ksic': j.get('induty_code'), 'ceo': j.get('ceo_nm'), 'acc_mt': j.get('acc_mt'),
              'est': j.get('est_dt'), 'cls': j.get('corp_cls'), 'at': today}
    time.sleep(0.12)
save('data/company.json', {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'source': 'DART OpenAPI 기업개황', 'company': out})
print('company calls', calls, 'firms', len(out))
