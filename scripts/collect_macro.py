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
# KDI EPU
t = get('https://eiec.kdi.re.kr/bigdata/epu.do?startDate=201301&endDate=' + ym, headers={'Referer': 'https://eiec.kdi.re.kr/bigdata/index.do', 'X-Requested-With': 'XMLHttpRequest'})
arr = json.loads(t)
epu = [[str(r['date']), round(float(r['한국 EPU 지수']), 2)] for r in arr if r.get('한국 EPU 지수') not in (None, '')]
save('data/epu.json', {'updated': res['updated'], 'source': 'KDI 경제교육·정보센터 경제불확실성지수', 'epu': epu})
print('ecos', {k: (len(v), v[-1] if v else None) for k, v in res.items() if isinstance(v, list)}, 'epu', epu[-2:])
