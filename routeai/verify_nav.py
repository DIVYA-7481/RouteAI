import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check page divs with inline display styles
print("Pages with inline display styles:")
pages = re.findall(r'<div class="page[^"]*" id="page-([^"]+)"[^>]*>', content)
for p in pages:
    print("  page-" + p)

# Check navigate function
nav_idx = content.index("function navigate(page)")
print()
print("navigate() function (first 700 chars):")
print(content[nav_idx:nav_idx+700])
