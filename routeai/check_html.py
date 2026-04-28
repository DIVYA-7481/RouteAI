from html.parser import HTMLParser

class HTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        self.counts = {}
        self.void = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

    def handle_starttag(self, tag, attrs):
        if tag not in self.void:
            self.stack.append(tag)
        self.counts[tag] = self.counts.get(tag, 0) + 1

    def handle_endtag(self, tag):
        if tag in self.void:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            top = self.stack[-1] if self.stack else "empty"
            self.errors.append("Mismatched: </" + tag + "> (stack top: " + top + ")")

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

v = HTMLValidator()
v.feed(content)

print("=== ERRORS ===")
for e in v.errors[:15]:
    print(e)
print("Total errors: " + str(len(v.errors)))
print()
print("=== KEY ELEMENT COUNTS ===")
for tag in ['div','script','style','svg','table']:
    print("  " + tag + ": " + str(v.counts.get(tag, 0)))
print()
print("=== UNCLOSED TAGS (open stack at end) ===")
tail = v.stack[-10:] if len(v.stack) > 10 else v.stack
print(tail)
print("Stack depth: " + str(len(v.stack)))

# Check key IDs exist
import re
ids_to_check = [
    'page-dispatch', 'page-analytics', 'page-map', 'page-overview', 'page-load', 'page-inventory',
    'dis-step-0', 'dis-step-1', 'dis-step-2', 'dis-step-3',
    'dis-si-0', 'dis-si-1', 'dis-si-2', 'dis-si-3',
    'dis-sb-0', 'dis-sb-1', 'dis-sb-2', 'dis-sb-3',
    'dis-tbody', 'dis-drawer', 'dis-drawer-bg', 'dis-confirm-btn',
    'an-co2-xhair', 'an-co2-tt',
    'lo-svg', 'mini-map', 'map',
]
print()
print("=== REQUIRED IDs ===")
missing = []
for id_ in ids_to_check:
    found = ('id="' + id_ + '"') in content or ("id='" + id_ + "'") in content
    if not found:
        missing.append(id_)
        print("  MISSING: " + id_)

if not missing:
    print("  All " + str(len(ids_to_check)) + " required IDs found.")

# Check for duplicate IDs
print()
print("=== DUPLICATE IDs ===")
all_ids = re.findall(r'id=["\']([^"\']+)["\']', content)
seen = {}
for id_ in all_ids:
    seen[id_] = seen.get(id_, 0) + 1
dups = {k: v for k, v in seen.items() if v > 1}
if dups:
    for k, v in list(dups.items())[:10]:
        print("  DUPLICATE: " + k + " (" + str(v) + " times)")
else:
    print("  No duplicate IDs found.")

# Check JS functions referenced
print()
print("=== JS FUNCTION CHECKS ===")
funcs = ['disNextStep', 'disConfirmDispatch', 'disOpenDrawer', 'disCloseDrawer', 'disFilter', 'disInit',
         'anCO2Hover', 'navigate', 'showToaster', 'loInit', 'mpLoadState']
for fn in funcs:
    defined = ('function ' + fn + '(') in content or ('async function ' + fn + '(') in content
    called = (fn + '(') in content
    status = "OK" if defined and called else ("DEF_ONLY" if defined else ("CALL_ONLY" if called else "MISSING"))
    print("  " + fn + ": " + status)
