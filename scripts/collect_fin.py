"""분기: DART 다중회사 주요계정(fnlttMultiAcnt)으로 시점별 재무제표. 접수일(rcept_no 앞 8자리)을 함께 저장해 미래정보 없이 백테스트."""
import os, json, time, datetime
from common import get, save, load, corp_map, universe, num, DART
cm = corp_map(); U = [c for c in universe() if c in cm]
Y0 = int(os.environ.get('Y0', '2017')); today = datetime.date.today()
REP = [('11013', 'Q1'), ('11012', 'H1'), ('11014', 'Q3'), ('11011', 'FY')]
KEEP = {'자산총계': 'A', '부채총계': 'L', '자본총계': 'E', '매출액': 'S', '영업이익': 'OP', '당기순이익': 'NI', '법인세차감전 순이익': 'EBT'}
old = load('data/fin.json', {}).get('fin', {}) if os.environ.get('FULL') != '1' else {}
fin = {c: {r['p']: r for r in old.get(c, [])} for c in U}
years = range(Y0, today.year + 1) if os.environ.get('FULL') == '1' or not old else range(today.year - 1, today.year + 1)
calls = 0
for y in years:
    for rc, tag in REP:
        for i in range(0, len(U), 100):
            chunk = U[i:i + 100]
            t = get(f'https://opendart.fss.or.kr/api/fnlttMultiAcnt.json?crtfc_key={DART}&corp_code={",".join(cm[c] for c in chunk)}&bsns_year={y}&reprt_code={rc}')
            calls += 1; j = json.loads(t)
            if j.get('status') != '000': continue
            rows = {}
            for r in j['list']:
                c = r['stock_code']; k = KEEP.get(r['account_nm'].strip())
                if not k: continue
                d = rows.setdefault((c, r['fs_div']), {'p': f'{y}{tag}', 'rc': r['rcept_no'][:8], 'end': r['thstrm_dt'][:10]})
                is_flow = r['sj_div'] in ('IS', 'CIS')
                v = num(r.get('thstrm_add_amount')) if (is_flow and tag in ('H1', 'Q3') and r.get('thstrm_add_amount')) else num(r.get('thstrm_amount'))
                if v is not None: d[k] = v
            for (c, fs), d in rows.items():
                cur = fin.setdefault(c, {}).get(d['p'])
                if fs == 'CFS' or not cur or cur.get('fs') != 'CFS':
                    d['fs'] = fs; fin[c][d['p']] = d
            time.sleep(0.3)
out = {c: sorted(v.values(), key=lambda r: r['p']) for c, v in fin.items() if v}
save('data/fin.json', {'updated': datetime.datetime.utcnow().isoformat() + 'Z', 'source': 'DART OpenAPI 다중회사 주요계정 (연결 우선, 없으면 개별). 손익은 누적(연초~분기말) 기준', 'fin': out})
print('fin calls', calls, 'firms', len(out), 'rows', sum(len(v) for v in out.values()))
