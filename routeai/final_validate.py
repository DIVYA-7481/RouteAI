import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

print("=" * 60)
print("FINAL VALIDATION REPORT")
print("=" * 60)

# 1. Check for duplicate const declarations
print("\n1. DUPLICATE JS CONST CHECK:")
const_names = re.findall(r'const ([A-Z_]+)\s*=', content)
from collections import Counter
dups = {k: v for k, v in Counter(const_names).items() if v > 1}
if dups:
    for k, v in dups.items():
        print(f"   DUPLICATE: {k} ({v} times)")
else:
    print("   No duplicate const declarations found.")

# 2. Check page initial display states
print("\n2. PAGE INITIAL DISPLAY STATES:")
page_divs = re.findall(r'<div[^>]*id="page-([^"]+)"[^>]*style="([^"]*)"', content)
for name, style in page_divs:
    has_display = 'display' in style
    disp = re.search(r'display:([^;]+)', style)
    val = disp.group(1) if disp else 'NOT SET'
    status = "OK" if has_display else "WARNING - no display"
    print(f"   page-{name}: display={val} [{status}]")

# 3. Check navigate() function body
print("\n3. NAVIGATE() FUNCTION:")
nav_match = re.search(r'function navigate\(page\) \{(.+?)\n\}', content, re.DOTALL)
if nav_match:
    body = nav_match.group(1)
    checks = [
        ('sets display none', "p.style.display = 'none'"),
        ('uses PAGE_DISPLAY', 'PAGE_DISPLAY[page]'),
        ('sets target display', 'target.style.display'),
        ('updates sidebar', 'sb-item'),
        ('updates topbar', 'topbar-title'),
        ('updates hash', 'replaceState'),
    ]
    for label, pattern in checks:
        found = pattern in body
        print(f"   {'OK' if found else 'MISSING'}: {label}")

# 4. HTML validation
print("\n4. HTML STRUCTURE:")
from html.parser import HTMLParser
class V(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []; self.errors = []
        self.void = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def handle_starttag(self, tag, attrs):
        if tag not in self.void: self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag in self.void: return
        if self.stack and self.stack[-1] == tag: self.stack.pop()
        else: self.errors.append(f"Mismatched </{tag}>")
v = V(); v.feed(content)
print(f"   HTML parse errors: {len(v.errors)}")
print(f"   Unclosed tags: {len(v.stack)}")

# 5. Key IDs check
print("\n5. KEY ELEMENT IDs:")
ids = ['page-dispatch', 'page-analytics', 'page-overview', 'page-map',
       'dis-step-0', 'dis-step-3', 'dis-tbody', 'dis-drawer',
       'an-co2-xhair', 'an-co2-tt', 'dis-confirm-btn']
for id_ in ids:
    found = f'id="{id_}"' in content
    print(f"   {'OK' if found else 'MISSING'}: #{id_}")

# 6. CSS check
print("\n6. CSS PAGE RULES:")
if 'display:none !important' in content:
    print("   OK: .page {display:none !important}")
else:
    print("   WARNING: !important rule not found")
if '#page-dispatch.active' in content:
    print("   OK: #page-dispatch.active flex rule")

print("\n" + "=" * 60)
print("SERVER: Running at http://localhost:5000")
print("To test: hard refresh browser (Ctrl+Shift+R) then click Analytics")
print("=" * 60)
