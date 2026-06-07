# Ziliaozhan (资料栈) Project Context

## Architecture
- Static site generator: `site_builder.py`
- Reads `site_meta.json` (7 categories) + scans PDFs → generates HTML
- Nginx serves /var/www/materials, SSI enabled for theme switching
- Python 3 only, no external dependencies

## Commands
- `python3 site_builder.py`           → build + validate
- `python3 site_builder.py --build`    → build only
- `python3 site_builder.py --validate` → validate only
- `python3 site_builder.py --help`     → full docs

## Hard Rules (NEVER violate)
1. CSS in module-level constant, NOT inside f-strings (causes { } escaping bugs)
2. Zero ES6 in generated HTML: no classList, const, let, =>, fetch, addEventListener
3. Zero CSS var() - all colors hardcoded
4. WeChat browser (MicroMessenger 8.0.73) must work
5. Theme: Nginx SSI via <!--# if expr="$cookie_theme = light" -->
6. Dark default (#0F172A), light via .theme-light overrides
7. Primary color: #3B82F6
8. Subpages embed ALL_FILES as JSON in <script> tag for client-side search
9. All JS event handlers via .onclick property (event delegation on parent)
10. Validate after every build - exit code 1 if violations found

## File Layout
- /var/www/materials/site_builder.py  — main builder
- /var/www/materials/site_meta.json   — category definitions
- /var/www/materials/files.json       — generated file index
- /var/www/materials/study/gaokao/    — 2551 PDF files by year/subject
- /var/www/materials/cat/*.html       — generated category pages

## Anti-Patterns (DO NOT DO)
- Do NOT embed CSS inside f-strings (use string concat with CSS constant)
- Do NOT modify builder on server without validation
- Do NOT use sed/perl for HTML manipulation (use Python)
- Do NOT hand-write HTML (use template functions)
- Do NOT skip validation step

## Post-Build Checklist
- [ ] `python3 site_builder.py` exits 0
- [ ] Zero ES6 violations in validation output
- [ ] http://47.94.216.51/ loads correctly
- [ ] Theme toggle works (SSI processes <!--# if -->)
- [ ] http://47.94.216.51/study/gaokao/ pagination works
- [ ] Mobile responsive (check @media breakpoints)
