import re

with open(r'c:\Users\DIVYA\RouteAI\routeai\templates\index.html', 'rb') as f:
    raw = f.read()

print('BOM:', raw[:4].hex())
print('File size:', len(raw))

# Find the map navigation block
needle = b"page === 'map'"
idx = raw.find(needle)
print(f'needle found at: {idx}')
if idx >= 0:
    chunk = raw[max(0,idx-5):idx+250]
    print('Hex:')
    print(chunk.hex())
    print('Decoded:')
    print(repr(chunk.decode('utf-16-le','replace')[:100] if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else chunk.decode('utf-8','replace')))
