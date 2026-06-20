"""
Patch startTruckAnimation to give each truck random speed and bearing updates.
"""

HTML = r'c:\Users\DIVYA\RouteAI\routeai\templates\index.html'
with open(HTML, 'rb') as f:
    raw = f.read()

BOM = b'\xef\xbb\xbf'
has_bom = raw.startswith(BOM)
data = raw[len(BOM):] if has_bom else raw

needle = b'function startTruckAnimation('
func_start = data.find(needle)

# Find closing brace
depth = 0; i = func_start; func_end = -1
while i < len(data):
    if data[i:i+1] == b'{': depth += 1
    elif data[i:i+1] == b'}':
        depth -= 1
        if depth == 0: func_end = i + 1; break
    i += 1

old_func = data[func_start:func_end]

# New function: independent step speed per truck + smooth interpolation
new_func = (
    b'function startTruckAnimation(truck, markerObj) {\n'
    b'  const pts = flattenCoords(truck.coords);\n'
    b'  if (pts.length < 2) return null;\n'
    b'  // Independent random starting position and speed per truck\n'
    b'  let progress = Math.random();  // 0.0 - 1.0 position along full route\n'
    b'  const speed  = 0.004 + Math.random() * 0.003;  // route fraction per tick\n'
    b'  const total  = pts.length - 1;\n'
    b'  const iv = setInterval(() => {\n'
    b'    progress = (progress + speed) % 1;\n'
    b'    const raw  = progress * total;\n'
    b'    const idx  = Math.floor(raw);\n'
    b'    const frac = raw - idx;\n'
    b'    const p1   = pts[idx];\n'
    b'    const p2   = pts[Math.min(idx + 1, total)];\n'
    b'    const pos  = [p1[0] + (p2[0]-p1[0])*frac, p1[1] + (p2[1]-p1[1])*frac];\n'
    b'    const bearing = calcBearing(p1, p2);\n'
    b'    markerObj.setLatLng(pos);\n'
    b'    markerObj.setIcon(mkTruckIcon(truck.color, bearing));\n'
    b'  }, 120);\n'
    b'  return iv;\n'
    b'}'
)

data = data[:func_start] + new_func + data[func_end:]

out = (BOM if has_bom else b'') + data
with open(HTML, 'wb') as f:
    f.write(out)

print('Patched startTruckAnimation!')
print('progress variable:', b'let progress = Math.random()' in data)
print('speed variable:',    b'const speed  = 0.004' in data)
print('smooth lerp:',       b'const frac = raw - idx' in data)
