"""데이터 원천 시험: 어떤 API가 GitHub Actions에서 응답하는지, 통계 코드가 맞는지 확인하고 결과를 data/_probe/에 저장."""
import os, json, io, zipfile, time, traceback, urllib.request, urllib.parse
OUT = 'data/_probe'; os.makedirs(OUT, exist_ok=True)
DART = os.environ.get('DART_API_KEY', ''); ECOS = os.environ.get('ECOS_API_KEY', '')
log = {}
def get(url, binary=False, headers=None, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read(); return b if binary else b.decode('utf-8', 'replace')
def safe(name, fn):
    try: log[name] = fn()
    except Exception as e: log[name] = {'error': repr(e)[:500]}
def mask(s): return s.replace(ECOS, '***').replace(DART, '***') if s else s

# ---- ECOS: 통계표 목록에서 후보 검색
def ecos_tables():
    t = get(f'https://ecos.bok.or.kr/api/StatisticTableList/{ECOS}/json/kr/1/10000')
    rows = json.loads(t).get('StatisticTableList', {}).get('row', [])
    kw = ['기준금리', '소비자물가지수', '국제수지', '증권투자', '외국인', '주식', '환율']
    hit = [r for r in rows if any(k in (r.get('STAT_NAME') or '') for k in kw)]
    return {'n': len(rows), 'hits': [{k: r.get(k) for k in ('STAT_CODE', 'STAT_NAME', 'CYCLE')} for r in hit][:300]}
safe('ecos_tables', ecos_tables)
def ecos_items(code):
    t = get(f'https://ecos.bok.or.kr/api/StatisticItemList/{ECOS}/json/kr/1/2000/{code}')
    rows = json.loads(t).get('StatisticItemList', {}).get('row', [])
    return [{k: r.get(k) for k in ('ITEM_CODE', 'ITEM_NAME', 'CYCLE', 'START_TIME', 'END_TIME', 'GRP_NAME')} for r in rows][:400]
for c in ['722Y001', '901Y009', '301Y013', '301Y017', '301Y014', '731Y001', '802Y001']:
    safe(f'ecos_items_{c}', lambda c=c: ecos_items(c))
def ecos_series(code, cyc, s, e, item):
    t = get(f'https://ecos.bok.or.kr/api/StatisticSearch/{ECOS}/json/kr/1/100/{code}/{cyc}/{s}/{e}/{item}')
    return json.loads(t)
safe('ecos_base_rate', lambda: ecos_series('722Y001', 'M', '202501', '202611', '0101000'))
safe('ecos_cpi', lambda: ecos_series('901Y009', 'M', '202501', '202611', '0'))

# ---- DART: 고유번호 파일 + 다중회사 주요계정 시험
def dart_corp():
    b = get(f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART}', binary=True)
    z = zipfile.ZipFile(io.BytesIO(b)); x = z.read(z.namelist()[0]).decode('utf-8')
    import re
    rows = re.findall(r'<corp_code>(\d+)</corp_code>\s*<corp_name>([^<]*)</corp_name>\s*(?:<corp_eng_name>[^<]*</corp_eng_name>\s*)?<stock_code>([^<]*)</stock_code>', x)
    m = {s.strip(): c for c, n, s in rows if s.strip()}
    json.dump(m, open(f'{OUT}/dart_corp_map.json', 'w'))
    return {'listed': len(m), 'samsung': m.get('005930')}
safe('dart_corp', dart_corp)
def dart_multi():
    m = json.load(open(f'{OUT}/dart_corp_map.json'))
    cc = ','.join([m['005930'], m['000660'], m['005380']])
    t = get(f'https://opendart.fss.or.kr/api/fnlttMultiAcnt.json?crtfc_key={DART}&corp_code={cc}&bsns_year=2025&reprt_code=11011')
    j = json.loads(t); return {'status': j.get('status'), 'message': j.get('message'), 'n': len(j.get('list', [])), 'sample': j.get('list', [])[:12]}
safe('dart_multi', dart_multi)

# ---- KRX (data.krx.co.kr) 직접 호출: VKOSPI 지수, 종목별 투자자 순매수
def krx(params):
    data = urllib.parse.urlencode(params).encode()
    t = get('http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd', data=data,
            headers={'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd', 'Content-Type': 'application/x-www-form-urlencoded'})
    return t[:3000]
safe('krx_vkospi', lambda: krx({'bld': 'dbms/MDC/STAT/standard/MDCSTAT00301', 'indIdx': '1', 'indIdx2': '300', 'strtDd': '20261001', 'endDd': '20261111'}))
safe('krx_investor_stock', lambda: krx({'bld': 'dbms/MDC/STAT/standard/MDCSTAT02302', 'isuCd': 'KR7005930003', 'strtDd': '20261001', 'endDd': '20261111', 'inqTpCd': '2', 'trdVolVal': '2', 'askBid': '3'}))
# ---- pykrx 시험
def pyk():
    from pykrx import stock
    df = stock.get_market_trading_value_by_date('20261001', '20261111', '005930')
    return {'cols': list(map(str, df.columns)), 'tail': df.tail(3).reset_index().astype(str).values.tolist()}
safe('pykrx_investor', pyk)
def pyk_idx():
    from pykrx import stock
    df = stock.get_index_ohlcv('20261001', '20261111', '1300')
    return {'tail': df.tail(3).reset_index().astype(str).values.tolist()}
safe('pykrx_vkospi', pyk_idx)
# ---- KDI EPU / Baker-Bloom-Davis Korea EPU
safe('kdi_epu', lambda: get('https://eiec.kdi.re.kr/bigdata/index.do')[:4000])
def bbd():
    b = get('https://www.policyuncertainty.com/media/Korea_Policy_Uncertainty_Data.xlsx', binary=True)
    import pandas as pd
    df = pd.read_excel(io.BytesIO(b)); return {'cols': list(map(str, df.columns)), 'tail': df.dropna().tail(4).astype(str).values.tolist()}
safe('bbd_korea_epu', bbd)
# ---- investing / stooq VKOSPI 대안
safe('stooq_vkospi', lambda: get('https://stooq.com/q/d/l/?s=^vkospi&i=d')[:500])

txt = mask(json.dumps(log, ensure_ascii=False, indent=1))
open(f'{OUT}/probe.json', 'w').write(txt)
print(txt[:3000])
