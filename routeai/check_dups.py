import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all PAGE_DISPLAY occurrences
lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'PAGE_DISPLAY' in line or 'page-map' in line and 'style=' in line:
        print(str(i).rjust(4) + ': ' + line[:100])
