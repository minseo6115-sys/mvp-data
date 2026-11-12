"""매일: 한국은행 ECOS(기준금리·CPI·공식 KOSPI/KOSDAQ 지수·시장별 외국인 순매수) + KDI 경제불확실성지수(EPU)."""
import json, datetime, urllib.parse
from common import get, save, ECOS
today = datetime.date.today()
def ecos(code, cyc, s, e, item, n=100000):
    out = []; start = 1
    while True:
        end = start + 9999
        t = get(f'https://ecos.bok.or.kr/api/StatisticSearch/{ECOS}/json/kr/{start}/{end}/{code}/{cyc}/{s}/{e}/{item}')
        j = json.loads(t).get('StatisticSearch', {}); rows = j.get('row', [])
        out += [[r['TIME'], float(r['DATA_VALUE'])] for r in rows if r.get('DATA_VALUE') not in (None, '')]
        if len(rows) < 10000: break
        start += 10000
    return out
res = {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'source': '한국은행 ECOS Open API'}
ym = today.strftime('%Y%m'); d8 = today.strftime('%Y%m%d')
res['bok_rate_m'] = ecos('722Y001', 'M', '201801', ym, '0101000')
res['bok_rate_d'] = ecos('722Y001', 'D', '20250101', d8, '0101000')
res['cpi_kr_m'] = ecos('901Y009', 'M', '201701', ym, '0')
for key, item in [('kospi', '0001000'), ('kosdaq', '0089000'), ('frgn_kospi', '0030000'), ('frgn_kosdaq', '0113000')]:
    res[key] = ecos('802Y001', 'D', '20180101', d8, item)
save('data/ecos.json', res)
# ---- 환율 연구용 장기 시계열(2010~): 원/달러, KOSPI, 국고채3년, 주요국 정책금리·CPI(국제피셔/금리평가)
lng = {'updated': res['updated'], 'source': '한국은행 ECOS Open API'}
for key, args in [('usdkrw', ('731Y001', 'D', '20100101', d8, '0000001')), ('kospi', ('802Y001', 'D', '20100101', d8, '0001000')),
                  ('ktb3y', ('817Y002', 'D', '20100101', d8, '010200000')), ('frgn_kospi', ('802Y001', 'D', '20100101', d8, '0030000'))]:
    try: lng[key] = ecos(*args)
    except Exception as e: lng[key] = []; print('long fail', key, type(e).__name__)
items = {}
for code in ('902Y006', '902Y008', '902Y021'):
    try:
        t = get(f'https://ecos.bok.or.kr/api/StatisticItemList/{ECOS}/json/kr/1/200/{code}')
        rows = json.loads(t).get('StatisticItemList', {}).get('row', [])
        items[code] = [[r.get('ITEM_CODE'), r.get('ITEM_NAME'), r.get('CYCLE')] for r in rows]
    except Exception as e: items[code] = repr(e)[:80]
lng['items'] = items
for code, store in (('902Y006', 'policy'), ('902Y008', 'cpi')):
    for it in (items.get(code) or []):
        if isinstance(it, list) and it[1] in ('미국', '한국', 'United States', 'Korea') and it[2] == 'M':
            try: lng[f'{store}_{it[0]}'] = ecos(code, 'M', '201001', ym, it[0])
            except Exception as e: pass
save('data/ecos_long.json', lng)
print('long', {k: len(v) for k, v in lng.items() if isinstance(v, list)})
# KDI EPU
t = get('https://eiec.kdi.re.kr/bigdata/epu.do?startDate=201301&endDate=' + ym, headers={'Referer': 'https://eiec.kdi.re.kr/bigdata/index.do', 'X-Requested-With': 'XMLHttpRequest'})
arr = json.loads(t)
epu = [[str(r['date']), round(float(r['한국 EPU 지수']), 2)] for r in arr if r.get('한국 EPU 지수') not in (None, '')]
save('data/epu.json', {'updated': res['updated'], 'source': 'KDI 경제교육·정보센터 경제불확실성지수', 'epu': epu})
print('ecos', {k: (len(v), v[-1] if v else None) for k, v in res.items() if isinstance(v, list)}, 'epu', epu[-2:])
# ---- VKOSPI (코스피200 변동성지수): KRX 사이트는 로그인이 필요해 investing.com 공개 API로 받음. 실패해도 다른 데이터에는 영향 없음
try:
    H = {'domain-id': 'www', 'Referer': 'https://www.investing.com/', 'Accept': 'application/json'}
    s = json.loads(get('https://api.investing.com/api/search/v2/search?q=KOSPI%20Volatility', headers=H, tries=2))
    cands = [q for q in s.get('quotes', []) if 'volatility' in (q.get('description', '') + q.get('name', '')).lower() and 'kospi' in (q.get('description', '') + q.get('name', '')).lower()]
    iid = cands[0]['id'] if cands else None
    vk = []
    if iid:
        y0 = (today.replace(day=1) - datetime.timedelta(days=800)).isoformat()
        h = json.loads(get(f'https://api.investing.com/api/financialdata/historical/{iid}?start-date={y0}&end-date={today.isoformat()}&time-frame=Daily&add-missing-rows=false', headers=H, tries=2))
        vk = sorted([[r['rowDateTimestamp'][:10], float(r['last_closeRaw'])] for r in h.get('data', [])])
    save('data/vkospi.json', {'updated': res['updated'], 'source': 'investing.com KOSPI Volatility (KSVKOSPI)', 'id': iid, 'cands': [[q.get('id'), q.get('description'), q.get('symbol')] for q in cands[:3]], 'vkospi': vk})
    print('vkospi', iid, len(vk), vk[-2:])
except Exception as e:
    print('vkospi failed', repr(e)[:200])
