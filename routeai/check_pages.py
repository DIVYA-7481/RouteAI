import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== PAGE DIV BOUNDARIES ===")
for i, line in enumerate(lines, 1):
    if 'id="page-' in line or '<!-- /page-' in line or 'PAGE 6' in line or 'PAGE 3' in line:
        print(str(i).rjust(4) + ': ' + line.rstrip()[:120])

print()
print("=== div open/close balance around dispatch/analytics ===")
depth = 0
in_dispatch = False
in_analytics = False
dispatch_start = 0
analytics_start = 0

for i, line in enumerate(lines, 1):
    opens = line.count('<div') - line.count('</div') - line.count('<div/>')
    
    if 'id="page-dispatch"' in line:
        in_dispatch = True
        dispatch_start = i
        depth = 0
        print(f"DISPATCH starts line {i}, depth resets to 0")
    elif 'id="page-analytics"' in line:
        in_analytics = True
        analytics_start = i
        depth = 0
        print(f"ANALYTICS starts line {i}, depth resets to 0")
    
    if in_dispatch and not in_analytics:
        depth += opens
        if depth == 0 and i > dispatch_start:
            print(f"DISPATCH closes at line {i}: {line.rstrip()[:80]}")
            in_dispatch = False
    elif in_analytics:
        depth += opens
        if depth == 0 and i > analytics_start:
            print(f"ANALYTICS closes at line {i}: {line.rstrip()[:80]}")
            in_analytics = False
