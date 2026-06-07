#!/usr/bin/env python3
import sys
from pathlib import Path

SITE = Path('/var/www/materials')
TARGETS = [SITE / 'index.html'] + list((SITE / 'cat').glob('*.html')) + list((SITE / 'study').rglob('index.html'))

BAD_PATTERNS = [
    ('classList', 'ES6'),
    ('const ', 'ES6'),
    ('let ', 'ES6'),
    ('=>', 'ES6 arrow'),
    ('fetch(', 'ES6'),
    ('addEventListener', 'ES6'),
    ('var(', 'CSS'),
]

ENGLISH_WORDS = ['Browse', 'Learn more', 'Total Files', 'Recently Updated', 'Search files', 'Latest Files', 'No files yet', 'By Category']

failed = 0
for fp in TARGETS:
    if not fp.exists():
        print('MISSING: ' + fp.name)
        failed += 1
        continue
    c = fp.read_text(encoding='utf-8')

    for pat, label in BAD_PATTERNS:
        n = c.count(pat)
        if n > 0:
            print('FAIL ' + fp.name + ': ' + str(n) + 'x ' + pat + ' (' + label + ')')
            failed += 1

    if '<span class="theme-link"' in c:
        opens = c.count('<span class="theme-link')
        bad = c.count('</a>')
        if bad > opens:
            print('FAIL ' + fp.name + ': </a> closing <span> tag mismatch')
            failed += 1

    if 'expr=\\"\\$cookie' in c:
        print('FAIL ' + fp.name + ': SSI escaped quote (use single quotes)')
        failed += 1

    for w in ENGLISH_WORDS:
        if w in c:
            print('FAIL ' + fp.name + ': English text "' + w + '"')
            failed += 1

    if 'className.indexOf' not in c:
        print('FAIL ' + fp.name + ': missing JS theme toggle')
        failed += 1

if failed == 0:
    print('ALL CLEAN - ' + str(len(TARGETS)) + ' pages')
    sys.exit(0)
else:
    print('FAILED: ' + str(failed) + ' issues')
    sys.exit(1)
