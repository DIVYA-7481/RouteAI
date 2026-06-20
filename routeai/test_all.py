"""
Full end-to-end test - fixed 401 handling and truck anim check
"""
import urllib.request, urllib.error, json, time, sys

BASE = 'http://127.0.0.1:5000'
PASS = []; FAIL = []

def get(path, timeout=8):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read())

def post(path, body, timeout=8):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(BASE + path, data=data,
           headers={'Content-Type':'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def check(name, cond, detail=''):
    if cond:
        PASS.append(name); print(f'  [PASS] {name}')
    else:
        FAIL.append(name); print(f'  [FAIL] {name}  {detail}')

print('\n=== Bug Fix Verification ===\n')

# Bug 9: Firebase
print('Bug 9 - Firebase persistence')
h = get('/api/health')
check('Firebase LIVE', h.get('firebase_status') == 'connected', h.get('firebase_status'))

# Bug 7: Hub status
print('\nBug 7 - Hub status endpoint')
hs = get('/api/hub/status')
check('/api/hub/status returns hubs',  'hubs' in hs)
check('Has at least 8 hubs',           len(hs.get('hubs',[])) >= 8)
check('Each hub has status+total',      all('status' in h and 'total' in h for h in hs.get('hubs',[])))
print(f'  Sample: {hs["hubs"][0]}')

# RiskAgent fix
print('\nRiskAgent.analyze() fix')
d, _ = post('/api/state/disrupted', {'headline': 'NH44 flooded near Krishnagiri, road blocked'})
check('Disruption POST returns trucks',  'trucks' in d)
check('Road extracted from headline',    d.get('disruption',{}).get('road','').startswith('NH'))

# Bug 12: HTML truck animation patches
print('\nBug 12 - Truck animation patches')
with open(r'templates\index.html','rb') as f: html = f.read()
check('Mini-map deferred to showDashboard', b'Mini-map deferred' in html)
check('Map nav always inits full map',      b'if (!mapInstance) { initFullMap()' in html)
check('invalidateSize in showDashboard',    b'miniMap.invalidateSize()' in html)

# Bug 13: Hubs on map
print('\nBug 13 - Hub markers on map')
state = get('/api/state/normal')
check('Normal state has trucks',            len(state.get('trucks',[])) > 0)
check('Nodes include hubs',                 len(state.get('nodes',[])) >= 5)

# Analytics
print('\nAnalytics')
an = get('/api/analytics')
check('co2_chart with 7 days',     len(an.get('co2_chart',{}).get('labels',[])) == 7)
check('dispatches_today is int',   isinstance(an['fleet_summary']['total_dispatches_today'], int))
check('co2_saved present',         an['fleet_summary']['co2_saved_vs_naive'] >= 0)

# Highway
print('\nHighway status')
hw = get('/api/highway')
check('All 5 NHs present', all(k in hw['highways'] for k in ['NH44','NH48','NH65','NH16','NH544']))

# Auth
print('\nAuth (login)')
lg, code  = post('/api/login', {'emp_id':'EMP001','password':'admin123'})
check('Admin login OK',           lg.get('success') is True and code == 200)
lg2, code2 = post('/api/login', {'emp_id':'EMP001','password':'WRONG'})
check('Wrong password -> 401',     code2 == 401)

print(f'\n{"="*42}')
print(f'  PASSED: {len(PASS)}   FAILED: {len(FAIL)}')
if FAIL:
    print('  Failed:')
    for f in FAIL: print(f'    - {f}')
print('='*42)
sys.exit(0 if not FAIL else 1)
