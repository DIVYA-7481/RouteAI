"""
Find and patch the truck animation logic in index.html.
"""

HTML = r'c:\Users\DIVYA\RouteAI\routeai\templates\index.html'
with open(HTML, 'rb') as f:
    raw = f.read()

BOM = b'\xef\xbb\xbf'
has_bom = raw.startswith(BOM)
data = raw[len(BOM):] if has_bom else raw

# Find the function
needle = b'function startTruckAnimation('
func_start = data.find(needle)
print(f'Found at: {func_start}')

# Show the full function
depth = 0; i = func_start; func_end = -1
while i < len(data):
    if data[i:i+1] == b'{':
        depth += 1
    elif data[i:i+1] == b'}':
        depth -= 1
        if depth == 0:
            func_end = i + 1
            break
    i += 1

old_func = data[func_start:func_end]
# Write to temp file to inspect without encoding issues
with open('anim_old.txt', 'wb') as f:
    f.write(old_func)
print(f'Function length: {len(old_func)} bytes, written to anim_old.txt')

# Also find the setInterval-based bulk animator if any
si_idx = data.find(b'truckAnimInterval = setInterval')
print(f'truckAnimInterval at: {si_idx}')
if si_idx >= 0:
    with open('anim_interval.txt','wb') as f:
        f.write(data[max(0,si_idx-200):si_idx+400])
    print('Written to anim_interval.txt')
