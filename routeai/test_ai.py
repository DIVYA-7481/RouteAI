from app import app
c = app.test_client()
r = c.post('/api/login', json={'emp_id': 'EMP001', 'password': 'admin123'})
token = r.get_json().get('token','')
h = {'Authorization': f'Bearer {token}'}

r = c.get('/api/fleet', headers=h)
fleet = r.get_json().get('fleet', [])

# Scenario 1: Mumbai -> Chennai, 400kg, MEDIUM
print("=== Scenario 1: Mumbai -> Chennai, 400kg, MEDIUM ===")
for t in fleet:
    remaining = t['capacity_kg'] - t['current_load_kg']
    selectable = t['selectable'] and remaining >= 400
    tc = (t.get('origin') or '').upper()
    if tc == 'CHE': tc = 'BEN'
    score = -1
    reason = 'NOT SELECTABLE'
    if selectable:
        score = (100 - t['load_pct']) * 0.3
        if t['status'] == 'IDLE': score += 30
        elif t['status'] == 'SCHEDULED': score += 15
        if tc == 'MUM': score += 25
        if t['type'] == 'Heavy': score += 10
        util_after = 400 / remaining
        if 0.4 <= util_after <= 0.8: score += 15
        elif util_after > 0.8: score += 5
        else: score += 8
        reason = f"load={t['load_pct']}% city={tc}"
    print(f"  {t['id']}: {score if score>0 else '-':>5}  {reason}")

# Scenario 2: Hyderabad -> Vizag, 180kg, URGENT
print("\n=== Scenario 2: Hyderabad -> Vizag, 180kg, URGENT ===")
for t in fleet:
    remaining = t['capacity_kg'] - t['current_load_kg']
    selectable = t['selectable'] and remaining >= 180
    tc = (t.get('origin') or '').upper()
    score = -1
    reason = 'NOT SELECTABLE'
    if selectable:
        score = (100 - t['load_pct']) * 0.3
        if t['status'] == 'IDLE': score += 30
        if tc == 'HYD': score += 25
        if t['type'] == 'Heavy': score += 15
        util_after = 180 / remaining
        if 0.4 <= util_after <= 0.8: score += 15
        reason = f"load={t['load_pct']}% city={tc} type={t['type']}"
    print(f"  {t['id']}: {score if score>0 else '-':>5}  {reason}")

# Scenario 3: Chennai -> Bengaluru, 500kg, HIGH
print("\n=== Scenario 3: Chennai -> Bengaluru, 500kg, HIGH ===")
for t in fleet:
    remaining = t['capacity_kg'] - t['current_load_kg']
    selectable = t['selectable'] and remaining >= 500
    tc = (t.get('origin') or '').upper()
    if tc == 'CHE': tc = 'BEN'
    score = -1
    reason = 'NOT SELECTABLE'
    if selectable:
        score = (100 - t['load_pct']) * 0.3
        if t['status'] == 'IDLE': score += 30
        if tc == 'BEN': score += 25
        if t['type'] == 'Heavy': score += 10
        util_after = 500 / remaining
        if 0.4 <= util_after <= 0.8: score += 15
        elif util_after > 0.8: score += 5
        reason = f"load={t['load_pct']}% city={tc} util={int(util_after*100)}%"
    print(f"  {t['id']}: {score if score>0 else '-':>5}  {reason}")
