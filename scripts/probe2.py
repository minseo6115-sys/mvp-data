"""시험 2: KDI EPU 데이터 경로, 네이버 외국인 매매 파싱, 구글 뉴스 RSS, VKOSPI 대체 경로."""
import os, json, re, urllib.request, urllib.parse
OUT = 'data/_probe'; os.makedirs(OUT, exist_ok=True); log = {}
def get(url, binary=False, headers=None, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read(); return b if binary else b.decode('utf-8', 'replace')
def safe(n, f):
    try: log[n] = f()
    except Exception as e: log[n] = {'error': repr(e)[:400]}
safe('kdi_epu_do', lambda: get('https://eiec.kdi.re.kr/bigdata/epu.do', data=urllib.parse.urlencode({'startDate': '201301', 'endDate': '202610'}).encode(),
     headers={'Referer': 'https://eiec.kdi.re.kr/bigdata/index.do', 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded'})[:3000])
safe('kdi_epu_get', lambda: get('https://eiec.kdi.re.kr/bigdata/epu.do?startDate=201301&endDate=202610', headers={'Referer': 'https://eiec.kdi.re.kr/bigdata/index.do', 'X-Requested-With': 'XMLHttpRequest'})[:3000])
def nf():
    t = get('https://finance.naver.com/item/frgn.naver?code=005930&page=1', binary=True).decode('euc-kr', 'replace')
    rows = re.findall(r'<td class="tc"><span class="tah p10 gray03">([\d.]+)</span></td>(.*?)</tr>', t, re.S)
    out = []
    for d, rest in rows[:5]:
        nums = re.findall(r'<span class="tah p11[^"]*">\s*([-+\d,.%]+)\s*</span>', rest)
        out.append([d] + nums)
    last = re.findall(r'page=(\d+)"[^>]*>\s*맨뒤', t)
    return {'rows': out, 'lastpage': last}
safe('naver_frgn_parse', nf)
def gnews():
    q = urllib.parse.quote('삼성전자 when:7d')
    t = get(f'https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko')
    items = re.findall(r'<item><title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>', t, re.S)
    return {'n': len(items), 'sample': items[:5]}
safe('google_news', gnews)
safe('daum_vkospi', lambda: get('https://finance.daum.net/api/domestic/sectors/VKOSPI/days?perPage=5', headers={'Referer': 'https://finance.daum.net/'})[:800])
safe('krx_openapi', lambda: get('https://data-dbg.krx.co.kr/svc/apis/idx/drvprod_dd_trd?basDd=20261110')[:800])
safe('naver_sise_kosdaq', lambda: get('https://finance.naver.com/sise/sise_index_day.naver?code=KOSDAQ&page=1', binary=True).decode('euc-kr','replace')[:200])
safe('investing_vkospi', lambda: get('https://api.investing.com/api/financialdata/historical/1166240?start-date=2026-10-01&end-date=2026-11-11&time-frame=Daily&add-missing-rows=false', headers={'domain-id': 'www'})[:800])
open(f'{OUT}/probe2.json', 'w').write(json.dumps(log, ensure_ascii=False, indent=1)); print(json.dumps(log, ensure_ascii=False)[:2000])
