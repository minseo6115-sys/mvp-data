"""매일: (1) DART 공시 중 주가에 큰 영향을 주는 경영 이벤트, (2) 구글 뉴스에서 오너·경영 리스크 키워드.
과거 전체(2019~)는 BACKFILL=1 로 한 번 실행."""
import os, json, re, time, datetime, urllib.parse, html
from common import get, save, load, corp_map, universe, names, DART
BACK = os.environ.get('BACKFILL') == '1'
today = datetime.date.today()
# 공시 분류: (키, 표시명, 방향 -1 악재/+1 호재/0 중립, 정규식)
RULES = [
 ('embezzle', '횡령·배임 발생', -1, r'횡령|배임'),
 ('lawsuit', '소송 제기', -1, r'소송등의제기|소송등의판결'),
 ('audit', '감사의견 비적정', -1, r'감사의견.*(거절|한정|부적정)|의견거절|감사범위제한'),
 ('halt', '거래정지·관리종목', -1, r'매매거래정지|관리종목|상장적격성|투자주의환기|불성실공시법인'),
 ('rights', '유상증자', -1, r'유상증자결정'),
 ('cb', '전환사채·BW 발행', -1, r'전환사채권발행결정|신주인수권부사채권발행결정|교환사채권발행결정'),
 ('owner', '최대주주 변경', 0, r'최대주주변경'),
 ('ceo', '대표이사 변경', 0, r'대표이사변경|대표이사\(대표집행임원\)변경'),
 ('buyback', '자사주 취득', 1, r'자기주식취득결정|자기주식취득신탁계약체결결정'),
 ('cancel', '자사주 소각', 1, r'주식소각결정'),
 ('dividend', '배당 결정', 1, r'현금ㆍ현물배당결정|현금·현물배당결정'),
 ('contract', '대규모 공급계약', 1, r'단일판매ㆍ공급계약체결|단일판매·공급계약체결'),
 ('earn', '잠정실적 공시', 0, r'영업\(잠정\)실적|연결재무제표기준영업\(잠정\)실적'),
 ('mna', '합병·분할·영업양수도', 0, r'회사합병결정|회사분할결정|영업양수결정|영업양도결정|타법인주식및출자증권양수결정'),
]
def classify(nm):
    for k, lab, d, pat in RULES:
        if re.search(pat, nm.replace(' ', '')): return k, lab, d
    return None
cm = corp_map(); U = universe(); NM = names()
prev = load('data/dart_events.json', {'events': {}})
ev = prev.get('events', {})
# BACKFILL: 2019년부터. 이미 받은 종목(done)은 건너뛰고, 실행 시간이 길어지면 중간 저장 후 종료 → 다음 실행이 이어서 받음
done = set(prev.get('back_done', [])) if BACK else set()
bgn0 = '20190101'
end = today.strftime('%Y%m%d')
T0 = time.time(); LIMIT = float(os.environ.get('TIME_LIMIT', '6600'))
calls = 0
def dump():
    save('data/dart_events.json', {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'source': 'DART 전자공시 OpenAPI (list.json)',
                                   'rules': [[k, lab, d] for k, lab, d, _ in RULES], 'events': ev,
                                   'back_done': sorted(done), 'back_complete': all(c in done for c in U if cm.get(c))})
for n, c in enumerate(U):
    cc = cm.get(c)
    if not cc: continue
    if BACK and c in done: continue
    if BACK and time.time() - T0 > LIMIT: print('time limit, stop at', n); break
    bgn = bgn0 if BACK else (today - datetime.timedelta(days=40)).strftime('%Y%m%d')
    got = {e['no']: e for e in ev.get(c, [])}
    page = 1; ok = True
    while True:
        try: t = get(f'https://opendart.fss.or.kr/api/list.json?crtfc_key={DART}&corp_code={cc}&bgn_de={bgn}&end_de={end}&page_no={page}&page_count=100', timeout=20, tries=3)
        except Exception as e: print('err', c, repr(e)[:80]); ok = False; break
        calls += 1; j = json.loads(t)
        if j.get('status') == '020': print('rate limit'); ok = False; break
        if j.get('status') not in ('000',): break
        for r in j.get('list', []):
            k = classify(r['report_nm'])
            if k: got[r['rcept_no']] = {'no': r['rcept_no'], 'd': r['rcept_dt'], 'k': k[0], 'nm': r['report_nm'].strip()[:60], 'dir': k[2]}
        if page >= int(j.get('total_page', 1)): break
        page += 1; time.sleep(0.1)
    ev[c] = sorted(got.values(), key=lambda e: e['d'])
    if BACK and ok: done.add(c)
    if BACK and n % 25 == 0: dump(); print('progress', n, len(done), 'calls', calls, int(time.time() - T0), 's', flush=True)
    if not ok and j.get('status') == '020': break
    time.sleep(0.05)
dump()
print('dart calls', calls, 'events', sum(len(v) for v in ev.values()), 'back_done', len(done))
if BACK: raise SystemExit
# ---- 뉴스 리스크 (최근 14일)
NEWS = [
 ('owner', '오너·경영진 리스크', r'구속|기소|영장|압수수색|검찰|횡령|배임|갑질|성추문|불륜|스캔들|마약|도박|폭행|사법리스크|오너리스크'),
 ('account', '회계·공시 신뢰', r'분식|회계부정|감사의견|거래정지|상장폐지|불성실공시|정정공시'),
 ('ops', '사업·운영 사고', r'리콜|화재|폭발|사망사고|중대재해|파업|공장 가동 중단|가동중단|생산 중단|해킹|개인정보 유출|품질 문제'),
 ('reg', '규제·제재', r'과징금|공정위|제재|소송|벌금|조사 착수|세무조사|수출 규제|반덤핑'),
 ('fin', '재무 악재', r'유상증자|전환사채|어닝쇼크|적자전환|영업손실|부도|워크아웃|회생'),
 ('good', '호재', r'어닝서프라이즈|사상 최대|최대 실적|수주|자사주 소각|자사주 매입|배당 확대|흑자전환|신고가'),
]
CUR = [s['code'] for s in json.load(open('universe.json'))['codes']][:]
cur110 = set(load('current110.json', []) or [])
targets = [c for c in CUR if (not cur110) or c in cur110]
news = {}
for c in targets:
    nm = NM.get(c, '')
    if not nm: continue
    q = urllib.parse.quote(f'"{nm}" when:14d')
    try: t = get(f'https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko', timeout=20, tries=2)
    except Exception: continue
    items = re.findall(r'<item><title>(.*?)</title><link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>.*?<source[^>]*>(.*?)</source>', t, re.S)
    hits = []
    for title, link, pub, src in items[:60]:
        title = html.unescape(title)
        if nm not in title: continue
        cats = [k for k, lab, pat in NEWS if re.search(pat, title)]
        if cats: hits.append({'t': title[:120], 'd': pub, 's': html.unescape(src)[:30], 'c': cats, 'u': link})
    news[c] = {'n': len(items), 'hits': hits[:12]}
    time.sleep(0.6)
save('data/news_risk.json', {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'source': 'Google 뉴스 RSS (최근 14일, 제목 키워드 분류)',
                             'cats': [[k, lab] for k, lab, _ in NEWS], 'news': news})
print('news', len(news), sum(len(v['hits']) for v in news.values()))
