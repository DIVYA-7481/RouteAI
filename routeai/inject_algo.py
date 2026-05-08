import re, os
base = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(base, 'templates', 'index.html')
content_path = os.path.join(base, 'algo_content.html')
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()
with open(content_path, 'r', encoding='utf-8') as f:
    content = f.read()
html = html.replace('    <!-- ALGO-VALIDATION-CONTENT-PLACEHOLDER -->', content)
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('Done - injected algo-validation content')
