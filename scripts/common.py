import os, json, time, urllib.request, urllib.parse, io, zipfile, re
DART = os.environ.get('DART_API_KEY', ''); ECOS = os.environ.get('ECOS_API_KEY', '')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
def get(url, binary=False, headers=None, data=None, timeout=30, tries=3):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={'User-Agent': UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read(); return b if binary else b.decode('utf-8', 'replace')
        except Exception as e:
            last = e; time.sleep(2 + 3 * k)
    raise last
def scrub(s):
    for k in (DART, ECOS):
        if k: s = s.replace(k, '***')
    return s
def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    txt = scrub(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
    open(path, 'w').write(txt)
def load(path, default=None):
    try: return json.load(open(path))
    except Exception: return default
def corp_map():
    p = 'data/dart_corp_map.json'
    m = load(p)
    if m and time.time() - os.path.getmtime(p) < 20 * 86400: return m
    b = get(f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART}', binary=True)
    z = zipfile.ZipFile(io.BytesIO(b)); x = z.read(z.namelist()[0]).decode('utf-8')
    rows = re.findall(r'<corp_code>(\d+)</corp_code>\s*<corp_name>([^<]*)</corp_name>\s*(?:<corp_eng_name>[^<]*</corp_eng_name>\s*)?<stock_code>([^<]*)</stock_code>', x)
    m = {s.strip(): c for c, n, s in rows if s.strip()}
    save(p, m); return m
def universe(): return [u['code'] for u in json.load(open('universe.json'))['codes']]
def names(): return {u['code']: u['name'] for u in json.load(open('universe.json'))['codes']}
def num(s):
    try: return float(str(s).replace(',', ''))
    except Exception: return None
