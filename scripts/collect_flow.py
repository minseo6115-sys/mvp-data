"""종목별 외국인·기관 순매수 이력 (네이버 증권 모바일 API). TEST=1이면 응답 구조만 기록."""
import os, json, time, datetime
from common import get, save, load, universe
H = {'Referer': 'https://m.stock.naver.com/', 'Accept': 'application/json'}
if os.environ.get('TEST') == '1':
    out = {}
    for u in ['https://m.stock.naver.com/api/stock/005930/trend?pageSize=10&bizdate=20261111',
              'https://m.stock.naver.com/api/stock/005930/trend?pageSize=10',
              'https://api.stock.naver.com/stock/005930/trend?pageSize=10',
              'https://m.stock.naver.com/api/stock/005930/integration',
              'https://m.stock.naver.com/api/index/KOSPI/basic']:
        try: out[u] = get(u, headers=H, tries=1)[:1500]
        except Exception as e: out[u] = repr(e)[:200]
    save('data/_flow_test.json', out); print(json.dumps(out, ensure_ascii=False)[:3000]); raise SystemExit
