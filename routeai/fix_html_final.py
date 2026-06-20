#!/usr/bin/env python3
"""
fix_html_final.py — Targeted fix script for index.html
Fixes:
  1. Demo panel: show actual credentials for judges
  2. loRemoveItem: preserve PK format IDs (not S01 format)
  3. av-formula-d: fix infinity symbol display
  4. av-formula-g: fix alpha/beta symbol display
  5. Footer: update toggle button text to match new panel
"""
import re

HTML_PATH = r'c:\Users\DIVYA\RouteAI\routeai\templates\index.html'

with open(HTML_PATH, 'rb') as f:
    raw = f.read()

# Decode — file is UTF-8 but may have some CRLF sequences
content = raw.decode('utf-8', errors='replace')

fixes_applied = []

# ── FIX 1: Demo panel — show actual passwords for judges ─────────────────────
old1 = (
    '    <!-- Demo credentials (passwords not exposed \u2014 auth is server-side) -->\n'
    '    <div style="text-align:center;">\n'
    '      <button id="login-demo-toggle" onclick="toggleDemoCreds()">Need help? View demo employees \u203a</button>\n'
    '    </div>\n'
    '    <div id="login-demo-panel">\n'
    '      <span class="dc-warn">\U0001f512 Passwords verified server-side, never exposed in browser</span>\n'
    '      <code>EMP001</code> \u2192 Admin (All Hubs)<br>\n'
    '      <code>EMP101</code> \u2192 BEN Hub Manager<br>\n'
    '      <code>EMP201</code> \u2192 HYD Hub Manager<br>\n'
    '      <code>EMP301</code> \u2192 MUM Hub Manager<br>\n'
    '      <code>EMP401</code> \u2192 COC Hub Manager<br>\n'
    '      <span class="dc-warn" style="margin-top:6px;display:block;">Ask judge for test passwords, or type any EMP ID to verify the hub lookup</span>\n'
    '    </div>'
)
new1 = (
    '    <!-- Demo credentials for judges (collapsed by default) -->\n'
    '    <div style="text-align:center;">\n'
    '      <button id="login-demo-toggle" onclick="toggleDemoCreds()">Need help? View demo credentials \u203a</button>\n'
    '    </div>\n'
    '    <div id="login-demo-panel">\n'
    '      <span class="dc-warn">\u26a0\ufe0f For demo/judging purposes only</span>\n'
    '      <code>EMP001</code> / <code>admin123</code> \u2192 Admin (All Hubs)<br>\n'
    '      <code>EMP101</code> / <code>ben123</code> \u2192 BEN Hub Manager<br>\n'
    '      <code>EMP201</code> / <code>hyd123</code> \u2192 HYD Hub Manager<br>\n'
    '      <code>EMP301</code> / <code>mum123</code> \u2192 MUM Hub Manager<br>\n'
    '      <code>EMP401</code> / <code>coc123</code> \u2192 COC Hub Manager<br>\n'
    '    </div>'
)

if old1 in content:
    content = content.replace(old1, new1, 1)
    fixes_applied.append('FIX 1: Demo panel updated with actual passwords')
else:
    # Try CRLF variant
    old1_crlf = old1.replace('\n', '\r\n')
    new1_crlf = new1.replace('\n', '\r\n')
    if old1_crlf in content:
        content = content.replace(old1_crlf, new1_crlf, 1)
        fixes_applied.append('FIX 1 (CRLF): Demo panel updated with actual passwords')
    else:
        # Try without the Unicode arrow — file may have escaped it differently
        # Try line by line approach: look for the specific pattern
        if 'Need help? View demo employees' in content and 'Ask judge for test passwords' in content:
            # Replace the button text
            content = content.replace(
                'Need help? View demo employees \u203a</button>',
                'Need help? View demo credentials \u203a</button>',
                1
            )
            # Replace the "never exposed" text with warning
            content = content.replace(
                '\U0001f512 Passwords verified server-side, never exposed in browser</span>',
                '\u26a0\ufe0f For demo/judging purposes only</span>',
                1
            )
            # Add passwords next to each EMP code by replacing the credential lines
            # Replace EMP001 line
            content = content.replace(
                '<code>EMP001</code> \u2192 Admin (All Hubs)<br>',
                '<code>EMP001</code> / <code>admin123</code> \u2192 Admin (All Hubs)<br>',
                1
            )
            content = content.replace(
                '<code>EMP101</code> \u2192 BEN Hub Manager<br>',
                '<code>EMP101</code> / <code>ben123</code> \u2192 BEN Hub Manager<br>',
                1
            )
            content = content.replace(
                '<code>EMP201</code> \u2192 HYD Hub Manager<br>',
                '<code>EMP201</code> / <code>hyd123</code> \u2192 HYD Hub Manager<br>',
                1
            )
            content = content.replace(
                '<code>EMP301</code> \u2192 MUM Hub Manager<br>',
                '<code>EMP301</code> / <code>mum123</code> \u2192 MUM Hub Manager<br>',
                1
            )
            content = content.replace(
                '<code>EMP401</code> \u2192 COC Hub Manager<br>',
                '<code>EMP401</code> / <code>coc123</code> \u2192 COC Hub Manager<br>',
                1
            )
            # Remove the "Ask judge" line
            content = content.replace(
                '      <span class="dc-warn" style="margin-top:6px;display:block;">Ask judge for test passwords, or type any EMP ID to verify the hub lookup</span>\r\n',
                '',
                1
            )
            content = content.replace(
                '      <span class="dc-warn" style="margin-top:6px;display:block;">Ask judge for test passwords, or type any EMP ID to verify the hub lookup</span>\n',
                '',
                1
            )
            fixes_applied.append('FIX 1 (granular): Demo panel updated with actual passwords')
        else:
            fixes_applied.append('FIX 1: FAILED — could not find demo panel')

# ── FIX 2: loRemoveItem — preserve PK format IDs ──────────────────────────────
old2 = "  loShipments.forEach(function(s, i) { s.id = 'S' + String(i + 1).padStart(2, '0'); });"
new2 = (
    "  // Re-number only the PK prefix, preserve G/origin/dest suffix so IDs stay in PK format\n"
    "  loShipments.forEach(function(s, i) {\n"
    "    var m = (s.id || '').match(/^PK\\d+(G.*)$/);\n"
    "    s.id = 'PK' + String(i + 1) + (m ? m[1] : 'G001BENMUM');\n"
    "  });"
)
if old2 in content:
    content = content.replace(old2, new2, 1)
    fixes_applied.append('FIX 2: loRemoveItem now preserves PK format IDs')
else:
    fixes_applied.append('FIX 2: FAILED — loRemoveItem pattern not found')

# ── FIX 3: av-formula-d — fix infinity symbol (displayed as garbled) ─────────
# The corrupted version shows "dist[all]=\ufffd  except dist[W1]=0"
# It should show "dist[all]=\u221e except dist[W1]=0" (infinity)
for corrupt_inf in ['\ufffd', '?', '\u00e2\u0080\u00a6']:
    if f'dist[all]={corrupt_inf}  except' in content:
        content = content.replace(f'dist[all]={corrupt_inf}  except', 'dist[all]=\u221e except', 1)
        fixes_applied.append('FIX 3: av-formula-d infinity symbol fixed')
        break
    elif f'dist[all]={corrupt_inf}except' in content:
        content = content.replace(f'dist[all]={corrupt_inf}except', 'dist[all]=\u221e except', 1)
        fixes_applied.append('FIX 3: av-formula-d infinity symbol fixed (no space)')
        break

# ── FIX 4: av-formula-g — fix alpha/beta symbols ────────────────────────────
# Corrupted: "cost[edge]=\ufffdT+\ufffdF+?\ufffdR \ufffd 0 always"
# Should be: "cost[edge]=\u03b1T+\u03b2F+\u03b3R \u2265 0 always"
for old_alpha in ['\ufffd', '?']:
    if f'cost[edge]={old_alpha}T+' in content:
        content = content.replace(
            f'cost[edge]={old_alpha}T+{old_alpha}F+?{old_alpha}R {old_alpha} 0',
            'cost[edge]=\u03b1T+\u03b2F+\u03b3R \u2265 0',
            1
        )
        fixes_applied.append('FIX 4: av-formula-g alpha/beta/gamma symbols fixed')
        break

# ── FIX 5: toggleDemoCreds — update toggle text to match new panel ─────────────
old5 = "btn.textContent = open ? 'Hide demo employees \u2039' : 'Need help? View demo employees \u203a';"
new5 = "btn.textContent = open ? 'Hide demo credentials \u2039' : 'Need help? View demo credentials \u203a';"
if old5 in content:
    content = content.replace(old5, new5, 1)
    fixes_applied.append('FIX 5: toggleDemoCreds text updated')
else:
    # Try with the arrow as literal characters
    content = content.replace(
        "btn.textContent = open ? 'Hide demo employees \u2039' : 'Need help? View demo employees \u203a';",
        "btn.textContent = open ? 'Hide demo credentials \u2039' : 'Need help? View demo credentials \u203a';",
        1
    )
    if "Hide demo credentials" in content:
        fixes_applied.append('FIX 5 (alt): toggleDemoCreds text updated')
    else:
        fixes_applied.append('FIX 5: SKIPPED (text may already be correct or encoding differs)')

# ── Write output ──────────────────────────────────────────────────────────────
with open(HTML_PATH, 'wb') as f:
    f.write(content.encode('utf-8'))

print('Fixes applied:')
for fix in fixes_applied:
    print(' ', fix)
print(f'\nDone. File written: {HTML_PATH}')
