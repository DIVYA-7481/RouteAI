import re, sys

HTML = r'c:\Users\DIVYA\RouteAI\routeai\templates\index.html'

with open(HTML, 'rb') as f:
    raw = f.read()

# File has UTF-8 BOM - strip it for processing, re-add at end
BOM = b'\xef\xbb\xbf'
has_bom = raw.startswith(BOM)
data = raw[len(BOM):] if has_bom else raw

original_size = len(data)
results = []

def fix(name, old, new):
    global data
    count = data.count(old)
    if count:
        data = data.replace(old, new)
    results.append((name, count))

# ── Check what's already been applied ────────────────────────────────────────
print("Status checks:")
print("  nav-map fix applied:", b"if (!mapInstance) { initFullMap()" in data)
print("  mini-map deferred:", b"Mini-map deferred" in data)
print("  invalidateSize in showDashboard:", b"miniMap.invalidateSize()" in data)

# ── FIX 1: Remove premature initMiniMap in DOMContentLoaded ─────────────────
fix('deferred-mini-map-CRLF',
    b'  // Init mini map\r\n  requestAnimationFrame(() => {\r\n    initMiniMap();\r\n  });',
    b'  // Mini-map deferred to showDashboard() so app-root is visible first'
)
fix('deferred-mini-map-LF',
    b'  // Init mini map\n  requestAnimationFrame(() => {\n    initMiniMap();\n  });',
    b'  // Mini-map deferred to showDashboard() so app-root is visible first'
)

# ── FIX 2: showDashboard - init mini-map after making app visible ─────────────
# Find exact block
old2_crlf = b"  // Navigate to overview - guard: wait for navigate to be defined\r\n  const tryNav = () => {\r\n    if (typeof navigate === 'function') { navigate('overview'); }\r\n    else setTimeout(tryNav, 50);\r\n  };\r\n  tryNav();\r\n}"
old2_lf   = b"  // Navigate to overview - guard: wait for navigate to be defined\n  const tryNav = () => {\n    if (typeof navigate === 'function') { navigate('overview'); }\n    else setTimeout(tryNav, 50);\n  };\n  tryNav();\n}"
new2 = (b"  // Navigate to overview - guard: wait for navigate to be defined\n"
        b"  const tryNav = () => {\n"
        b"    if (typeof navigate === 'function') {\n"
        b"      navigate('overview');\n"
        b"      // Init mini-map AFTER app-root visible (fixes blank Fleet Map bug)\n"
        b"      requestAnimationFrame(() => {\n"
        b"        if (!miniMap) { initMiniMap(); }\n"
        b"        else { try { miniMap.invalidateSize(); } catch(e){} }\n"
        b"      });\n"
        b"    } else { setTimeout(tryNav, 50); }\n"
        b"  };\n"
        b"  tryNav();\n"
        b"}")
if data.count(old2_crlf): fix('showDashboard-minimap-CRLF', old2_crlf, new2)
elif data.count(old2_lf): fix('showDashboard-minimap-LF',   old2_lf,   new2)
else: results.append(('showDashboard-minimap', 0))

# ── FIX 3: Truck animation - independent speed per truck ─────────────────────
# Find startTruckAnimation via unique anchor
anchor = b"const t = (Date.now() / 8000) % 1;"
if anchor in data:
    # Replace just the body of the function
    fix('truck-anim-independent',
        anchor,
        b"tm._prog = ((Date.now()/1000 * tm._speed) + tm._offset) % 1;"
    )
    # Initialise _speed/_offset when spawning truck markers
    fix('truck-spawn-init',
        b"truckMarkers.push({marker, pts});",
        b"truckMarkers.push({marker, pts, _speed: 0.00007+Math.random()*0.00005, _offset: Math.random(), _prog:0});"
    )
    # Fix the broken iterator variable (was using {marker,pts} destructure but we need tm)
    fix('truck-anim-vars',
        b"truckMarkers.forEach(({marker, pts}) => {",
        b"truckMarkers.forEach((tm) => { const {marker, pts} = tm;"
    )
    fix('truck-anim-timing', b"}, 100);", b"}, 80);")

# ── FIX 4: Bug 7 - Add /api/hub/status call in refreshInventoryCounts ────────
# Prepend live fetch to existing function
old4 = b"async function refreshInventoryCounts() {"
new4 = (b"async function refreshInventoryCounts() {\n"
        b"  try {\n"
        b"    const r = await fetch('/api/hub/status');\n"
        b"    if (r.ok) {\n"
        b"      const d = await r.json();\n"
        b"      (d.hubs || []).forEach(h => {\n"
        b"        const el = document.getElementById('hub-count-' + h.hub_id);\n"
        b"        const st = document.getElementById('hub-status-' + h.hub_id);\n"
        b"        if (el) el.textContent = h.total;\n"
        b"        if (st) { st.textContent = h.total > 5 ? 'BUSY' : 'OK';\n"
        b"          st.className = h.total > 5 ? 'pill pill-red' : 'pill pill-green'; }\n"
        b"      });\n"
        b"    }\n"
        b"  } catch(e) {}\n")
if data.count(old4) == 1:
    fix('hub-status-live', old4, new4)
else:
    results.append(('hub-status-live (skipped - multiple matches)', data.count(old4)))

# ── FIX 5: Spelling errors ────────────────────────────────────────────────────
sp = [
    (b'Validaiton',     b'Validation'),
    (b'validaiton',     b'validation'),
    (b'Inventry',       b'Inventory'),
    (b'inventry',       b'inventory'),
    (b'Algorythm',      b'Algorithm'),
    (b'remianing',      b'remaining'),
    (b'abolute',        b'absolute'),
    (b'ResilientChian', b'ResilientChain'),
    (b'efficieny',      b'efficiency'),
    (b'Efficieny',      b'Efficiency'),
    (b'recieve',        b'receive'),
    (b'occured',        b'occurred'),
    (b'optimizater',    b'optimizer'),
    (b'Optimizater',    b'Optimizer'),
    (b'Ac OpenStreetMap', b'(c) OpenStreetMap'),
    (b'Ac CartoDB',     b'(c) CartoDB'),
    (b'avg response',   b'Avg Response'),
    (b'auto-tracked today', b'Auto-tracked today'),
]
for old, new in sp:
    fix('spell:' + old.decode('utf-8','ignore'), old, new)

# ── Write back with BOM ───────────────────────────────────────────────────────
out = (BOM if has_bom else b'') + data
with open(HTML, 'wb') as f:
    f.write(out)

print(f'\nFile: {original_size:,} -> {len(data):,} bytes')
for name, count in results:
    st = 'OK' if count > 0 else '--'
    print(f'  [{st}] {name}: {count}')
