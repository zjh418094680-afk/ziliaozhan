#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ziliaozhan Static Site Builder
================================
Reads site_meta.json, scans PDF files, generates static HTML pages.

Architecture:
  CSS     → module-level CSS constant (no f-string, no escaping issues)
  Templates → pure functions that return HTML strings
  Builders  → compose templates with data, write to disk
  Validator → checks generated HTML for ES6 violations
  CLI       → sys.argv: --build, --validate, or both (default)

Exit codes:
  0 = success
  1 = validation failed (ES6 violations found)
  2 = build error (missing files, write failure)

Usage:
  python3 site_builder.py              # build + validate
  python3 site_builder.py --build      # build only
  python3 site_builder.py --validate   # validate only
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

# ── Configuration ──────────────────────────────────────

SITE_ROOT   = Path(__file__).resolve().parent
META_PATH   = SITE_ROOT / "site_meta.json"
FILES_PATH  = SITE_ROOT / "files.json"
CATEGORY_DIR = SITE_ROOT / "cat"
SITE_NAME    = "Ziliaozhan"
SITE_TITLE   = "\u8d44\u6599\u6808"  # 资料栈

# ── CSS ────────────────────────────────────────────────
# Single source of truth for all page styles.
# Hardcoded colors (no var()), dual-theme (.theme-dark default + .theme-light overrides).
# WeChat browser (MicroMessenger 8.0.73) compatible.

CSS = (
    "*{margin:0;padding:0;box-sizing:border-box}"
    "html,body{overflow-x:hidden}"
    "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
    "'Noto Sans SC','Microsoft YaHei',sans-serif;background:#0F172A;color:#F1F5F9;"
    "line-height:1.6;min-height:100vh;-webkit-font-smoothing:antialiased}"
    ".theme-light body{background:#F8FAFC;color:#111827}"
    "a{color:inherit;text-decoration:none}"
    "::selection{background:rgba(59,130,246,.3);color:#fff}"
    "img{max-width:100%;height:auto}"
    ".navbar{position:sticky;top:0;z-index:100;background:rgba(15,23,42,.92);"
    "border-bottom:1px solid #334155;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}"
    ".theme-light .navbar{background:rgba(255,255,255,.9);border-color:#E5E7EB}"
    ".nav-inner,.wrap,.footer-inner{max-width:1200px;margin:0 auto}"
    ".nav-inner{min-height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 24px}"
    ".logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700;color:#F1F5F9;letter-spacing:-.3px}"
    ".theme-light .logo{color:#0F172A}"
    ".logo-icon{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#F7D08A,#D9A441,#8D5A2A);"
    "display:grid;place-items:center;box-shadow:0 4px 16px rgba(217,164,65,.25)}"
    ".logo-icon svg{width:22px;height:22px}"
    ".theme-btn{width:48px;height:28px;border-radius:99px;background:#334155;border:1.5px solid #475569;"
    "position:relative;overflow:hidden;flex-shrink:0}"
    ".theme-light .theme-btn{background:#CBD5E1;border-color:#94A3B8}"
    ".theme-link{position:absolute;inset:0;display:flex;align-items:center;text-decoration:none;color:inherit;z-index:2}"
    ".to-light{justify-content:flex-start;padding-left:7px}"
    ".to-dark{justify-content:flex-end;padding-right:7px}"
    ".theme-dark .to-dark{display:none}"
    ".theme-light .to-light{display:none}"
    ".theme-knob{position:absolute;top:2px;left:2px;z-index:1;width:22px;height:22px;border-radius:50%;"
    "background:#3B82F6;pointer-events:none;transition:left .28s ease;box-shadow:0 2px 8px rgba(0,0,0,.25)}"
    ".theme-light .theme-knob{left:22px;background:#FBBF24}"
    ".hero{position:relative;padding:clamp(56px,8vw,96px) 24px clamp(40px,6vw,72px);text-align:center;"
    "background:linear-gradient(135deg,#0F172A 0%,#1E293B 52%,#334155 100%)}"
    ".theme-light .hero{background:linear-gradient(135deg,#EFF6FF 0%,#DBEAFE 55%,#BFDBFE 100%)}"
    ".hero h1{font-size:clamp(32px,6vw,60px);line-height:1.1;font-weight:800;letter-spacing:-1px;"
    "color:#F8FAFC;margin-bottom:16px}"
    ".theme-light .hero h1{color:#0F172A}"
    ".hero h1 em{font-style:normal;background:linear-gradient(135deg,#3B82F6,#8B5CF6);"
    "-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}"
    ".hero p{font-size:clamp(15px,2vw,18px);color:#94A3B8;max-width:480px;margin:0 auto 32px}"
    ".theme-light .hero p{color:#6B7280}"
    ".btn{display:inline-flex;align-items:center;gap:8px;padding:12px 28px;border-radius:8px;"
    "font-size:15px;font-weight:600;border:none;cursor:pointer;transition:all .2s}"
    ".btn-primary{background:#3B82F6;color:#fff;box-shadow:0 4px 16px rgba(59,130,246,.3)}"
    ".btn-primary:hover{background:#2563EB;transform:translateY(-1px)}"
    ".btn-ghost{background:rgba(255,255,255,.03);color:#D0D6E0;border:1px solid rgba(255,255,255,.08)}"
    ".btn-ghost:hover{background:rgba(255,255,255,.06)}"
    ".theme-light .btn-ghost{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.08);color:#31302E}"
    ".hero-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:32px}"
    ".stats{display:flex;justify-content:center;gap:clamp(32px,6vw,64px);padding:0 24px 56px;flex-wrap:wrap}"
    ".stat{text-align:center}"
    ".stat-num{font-size:clamp(28px,4vw,40px);font-weight:800;color:#F8FAFC;letter-spacing:-.5px}"
    ".theme-light .stat-num{color:#0F172A}"
    ".stat-num-grad{background:linear-gradient(135deg,#3B82F6,#8B5CF6);-webkit-background-clip:text;"
    "-webkit-text-fill-color:transparent;background-clip:text}"
    ".stat-label{font-size:13px;color:#94A3B8;font-weight:500;margin-top:6px;text-transform:uppercase}"
    ".sec{padding:0 24px 72px}"
    ".sec-inner{max-width:1100px;margin:0 auto}"
    ".sec-tag{font-size:12px;font-weight:600;color:#3B82F6;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px}"
    ".sec-title{font-size:clamp(22px,3vw,32px);font-weight:700;color:#F8FAFC;margin-bottom:10px}"
    ".theme-light .sec-title{color:#0F172A}"
    ".sec-sub{font-size:14px;color:#94A3B8;margin-bottom:28px;max-width:480px}"
    ".cat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin-bottom:16px}"
    ".cat-card{display:flex;align-items:center;gap:14px;padding:18px 22px;border-radius:12px;"
    "background:#1E293B;border:1px solid #334155;transition:all .2s}"
    ".cat-card:hover{transform:translateY(-2px);border-color:#60A5FA;box-shadow:0 8px 24px rgba(0,0,0,.25)}"
    ".theme-light .cat-card{background:#fff;border-color:#E5E7EB;box-shadow:0 2px 8px rgba(0,0,0,.02)}"
    ".theme-light .cat-card:hover{box-shadow:0 8px 24px rgba(0,0,0,.05)}"
    ".cat-icon{width:44px;height:44px;border-radius:10px;display:grid;place-items:center;font-size:22px;"
    "flex-shrink:0;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06)}"
    ".theme-light .cat-icon{background:#F1F5F9;border-color:rgba(0,0,0,.05)}"
    ".cat-info{min-width:0;flex:1}"
    ".cat-name{font-size:15px;font-weight:600;color:#F8FAFC;margin-bottom:2px}"
    ".theme-light .cat-name{color:#0F172A}"
    ".cat-count{font-size:12px;color:#94A3B8}"
    ".cat-arrow{color:#4B5563;font-size:18px;flex-shrink:0;opacity:.4}"
    ".cat-card:hover .cat-arrow{color:#3B82F6;opacity:1}"
    ".file-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}"
    ".file-card{display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:8px;"
    "background:rgba(255,255,255,.015);border:1px solid rgba(255,255,255,.04);transition:all .2s}"
    ".file-card:hover{background:rgba(59,130,246,.05);border-color:rgba(59,130,246,.2);transform:translateY(-1px)}"
    ".theme-light .file-card{background:#fff;border-color:#E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,.01)}"
    ".fc-icon{width:32px;height:32px;border-radius:8px;flex-shrink:0;"
    "background:linear-gradient(135deg,rgba(239,68,68,.12),rgba(239,68,68,.04));border:1px solid rgba(239,68,68,.1);"
    "display:grid;place-items:center;font-size:10px;font-weight:700;color:#EF4444}"
    ".fc-info{min-width:0}"
    ".fc-name{font-size:12px;font-weight:500;color:#D0D6E0;white-space:nowrap;overflow:hidden;"
    "text-overflow:ellipsis;display:block}"
    ".theme-light .fc-name{color:#1F2937}"
    ".fc-date{font-size:10px;color:#94A3B8;margin-top:2px}"
    ".page-hero{padding:32px 24px 20px;background:linear-gradient(135deg,#0F172A 0%,#1E293B 52%,#334155 100%)}"
    ".theme-light .page-hero{background:linear-gradient(135deg,#EFF6FF 0%,#DBEAFE 55%,#BFDBFE 100%)}"
    ".breadcrumbs{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:13px;color:#94A3B8;margin-bottom:8px}"
    ".breadcrumbs a{color:#60A5FA}"
    ".page-title{font-size:clamp(24px,3vw,36px);font-weight:800;color:#F8FAFC;margin-top:8px}"
    ".theme-light .page-title{color:#0F172A}"
    ".page-desc{font-size:14px;color:#94A3B8;margin-top:4px}"
    ".chip-nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}"
    ".chip{display:inline-block;padding:5px 12px;border-radius:99px;background:#1E293B;border:1px solid #334155;"
    "font-size:12px;font-weight:500}"
    ".chip:hover{background:#2563EB;border-color:#2563EB;color:#fff}"
    ".chip.active{background:#3B82F6;border-color:#3B82F6;color:#fff}"
    ".theme-light .chip{background:#fff;border-color:#E5E7EB}"
    ".sub-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin:20px 0}"
    ".sub-card{display:block;padding:20px;border-radius:12px;background:#1E293B;border:1px solid #334155;transition:all .2s}"
    ".sub-card:hover{transform:translateY(-2px);border-color:#60A5FA}"
    ".theme-light .sub-card{background:#fff;border-color:#E5E7EB}"
    ".sub-icon{font-size:28px;margin-bottom:8px}"
    ".sub-name{font-size:15px;font-weight:700;color:#F8FAFC}"
    ".theme-light .sub-name{color:#0F172A}"
    ".sub-desc{font-size:12px;color:#94A3B8;margin-top:4px}"
    ".file-panel{background:#1E293B;border:1px solid #334155;border-radius:12px;overflow:hidden}"
    ".theme-light .file-panel{background:#fff;border-color:#E5E7EB}"
    ".fitem{display:grid;grid-template-columns:minmax(0,1fr) 100px 75px;gap:10px;padding:10px 16px;"
    "border-bottom:1px solid #334155;align-items:center}"
    ".theme-light .fitem{border-color:#E5E7EB}"
    ".fitem:last-child{border-bottom:none}"
    ".fitem:nth-child(odd){background:rgba(255,255,255,.015)}"
    ".theme-light .fitem:nth-child(odd){background:#F8FAFC}"
    ".fitem-name{font-size:13px;word-break:break-all}"
    ".fitem-name a:hover{color:#60A5FA}"
    ".fitem-date,.fitem-size{font-size:12px;color:#94A3B8;white-space:nowrap}"
    ".fitem-empty{padding:36px 16px;text-align:center;color:#94A3B8;font-size:13px}"
    ".toolbar{margin-bottom:10px}"
    ".search-input{width:100%;padding:10px 14px;border-radius:8px;border:1px solid #334155;"
    "background:#1E293B;color:#F1F5F9;font-size:13px;outline:none}"
    ".search-input:focus{border-color:#60A5FA}"
    ".search-input::placeholder{color:#64748B}"
    ".theme-light .search-input{background:#fff;border-color:#CBD5E1;color:#111827}"
    ".pg-bar{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;padding:12px 16px}"
    ".pg-size-select{padding:4px 8px;border-radius:6px;border:1px solid #334155;"
    "background:#1E293B;color:#F1F5F9;font-size:12px;outline:none}"
    ".pg-btn{display:inline-flex;align-items:center;justify-content:center;min-width:30px;height:30px;"
    "border-radius:6px;border:1px solid #334155;background:#1E293B;color:#D0D6E0;font-size:13px;"
    "font-weight:500;user-select:none;cursor:pointer}"
    ".pg-btn:hover{background:#2563EB;border-color:#2563EB;color:#fff}"
    ".pg-btn.active{background:#3B82F6;border-color:#3B82F6;color:#fff;font-weight:600}"
    ".pg-btn.disabled{opacity:.3;cursor:default}"
    ".pg-info{font-size:12px;color:#94A3B8;white-space:nowrap}"
    ".theme-light .pg-size-select,.theme-light .pg-btn{background:#fff;border-color:#CBD5E1;color:#111827}"
    ".footer{margin-top:40px;padding:40px 24px 24px;border-top:1px solid #334155;color:#94A3B8;font-size:12px}"
    ".theme-light .footer{border-color:#E5E7EB;color:#64748B}"
    ".footer-inner{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr;"
    "gap:28px;margin-bottom:24px}"
    ".footer-brand .logo{font-size:16px;margin-bottom:8px}"
    ".footer-brand p{font-size:12px;color:#94A3B8;line-height:1.6;max-width:280px}"
    ".footer-col h4{font-size:11px;font-weight:600;color:#94A3B8;text-transform:uppercase;"
    "letter-spacing:1.5px;margin-bottom:10px}"
    ".footer-col ul{list-style:none}"
    ".footer-col li{margin-bottom:6px}"
    ".footer-col a{font-size:12px;transition:color .2s}"
    ".footer-col a:hover{color:#60A5FA}"
    ".footer-bottom{max-width:1100px;margin:0 auto;padding-top:16px;border-top:1px solid #334155;"
    "display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:11px}"
    ".theme-light .footer-bottom{border-color:#E5E7EB}"
    ".footer-email{color:#3B82F6}"
    "@media(max-width:768px){.nav-inner,.wrap,.footer-inner{padding:0 16px}"
    ".hero{padding:48px 16px 32px}.cat-grid,.file-grid{grid-template-columns:1fr}"
    ".fitem{grid-template-columns:minmax(0,1fr) 80px 60px;gap:6px;padding:8px 12px}"
    ".sub-grid{grid-template-columns:1fr}.footer-inner{grid-template-columns:1fr;gap:20px}}"
    "@media(max-width:480px){.nav-inner{padding:0 12px}.logo{font-size:17px}"
    ".logo-icon{width:32px;height:32px}.sec{padding:0 16px 56px}.hero h1{font-size:28px}"
    ".btn{padding:10px 20px;font-size:14px}.cat-card{padding:14px 16px}"
    ".cat-icon{width:38px;height:38px;font-size:20px}"
    ".fitem{grid-template-columns:1fr;gap:4px;padding:8px 10px}.fitem-date,.fitem-size{font-size:11px}"
    ".theme-btn{width:54px;height:32px}.theme-knob{width:26px;height:26px;top:2px;left:2px}"
    ".theme-light .theme-knob{left:24px}.to-light{padding-left:8px;font-size:14px}"
    ".to-dark{padding-right:8px;font-size:14px}}"
)

# ── SVG Icons ──────────────────────────────────────────

LOGO_SVG = (
    '<svg viewBox="0 0 48 48" role="img">'
    '<defs><linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">'
    '<stop offset="0%" stop-color="#F7D08A"/><stop offset="40%" stop-color="#D9A441"/>'
    '<stop offset="72%" stop-color="#8D5A2A"/><stop offset="100%" stop-color="#557A62"/>'
    '</linearGradient></defs>'
    '<path d="M17 9h14l3 6H14l3-6Z" fill="url(#bg)" stroke="#111827" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M15 15h18v5H15z" fill="url(#bg)" stroke="#111827" stroke-width="1.4" stroke-linejoin="round"/>'
    '<path d="M14 19h20v8c0 4.6-3.4 8-8 8h-4c-4.6 0-8-3.4-8-8v-8Z" fill="url(#bg)" stroke="#111827" stroke-width="1.7" stroke-linejoin="round"/>'
    '<path d="M18 35h12l-1.8 3.5H19.8L18 35Z" fill="url(#bg)" stroke="#111827" stroke-width="1.4" stroke-linejoin="round"/>'
    '<path d="M24 4v3" fill="none" stroke="#111827" stroke-width="1.6" stroke-linecap="round"/>'
    '<circle cx="24" cy="24" r="2.1" fill="#F7D08A" stroke="#111827" stroke-width=".8"/></svg>'
)

LOGO_SVG_SMALL = LOGO_SVG.replace('viewBox="0 0 48 48"', 'viewBox="0 0 48 48" style="width:16px;height:16px"')

# ── HTML Templates ─────────────────────────────────────

def _navbar():
    """Return the shared navigation bar HTML."""
    return (
        '<nav class="navbar"><div class="nav-inner">'
        '<a href="/" class="logo"><span class="logo-icon" aria-hidden="true">'
        + LOGO_SVG + '</span><span>' + SITE_TITLE + '</span></a>'
        '<div class="theme-btn">'
        '<a class="theme-link to-light" href="/theme?set=light" aria-label="Switch to light">\u2600\ufe0f</a>'
        '<a class="theme-link to-dark" href="/theme?set=dark" aria-label="Switch to dark">\U0001f319</a>'
        '<span class="theme-knob" aria-hidden="true"></span>'
        '</div></div></nav>'
    )

def _footer(meta):
    """Return the shared footer HTML."""
    cat_links = "".join(
        '<li><a href="/cat/' + escape(c["slug"]) + '.html">' + escape(c["icon"]) + " " + escape(c["name"]) + "</a></li>"
        for c in meta["categories"]
    )
    return (
        '<footer class="footer"><div class="footer-inner">'
        '<div class="footer-brand"><div class="logo"><span class="logo-icon">'
        + LOGO_SVG_SMALL + "</span>" + escape(meta["site_name"])
        + '</div><p>Security, efficiency, convenience. Gaokao exams are public domain under Copyright Law Article 5.</p></div>'
        '<div class="footer-col"><h4>Resources</h4><ul><li><a href="/">Home</a></li>'
        + cat_links + '<li><a href="/about.html">About</a></li></ul></div>'
        '<div class="footer-col"><h4>Contact</h4><ul>'
        '<li><a href="mailto:' + escape(meta["contact_email"]) + '" class="footer-email">'
        + escape(meta["contact_email"]) + "</a></li>"
        '<li><a href="/privacy.html">Privacy</a></li><li><a href="/terms.html">Terms</a></li>'
        '</ul></div></div>'
        '<div class="footer-bottom"><span>&copy; 2026 ' + escape(meta["site_name"]) + "</span></div></footer>"
    )

def _page(title, body, meta):
    """Wrap body in full HTML document with CSS, navbar, and footer."""
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN" class="<!--# if expr=\\"$cookie_theme = light\\" -->theme-light<!--# else -->theme-dark<!--# endif -->">\n'
        '<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>" + escape(title) + "</title>\n"
        '<link rel="icon" href="/favicon.ico">\n<style>\n' + CSS + "\n</style>\n</head>\n<body>\n"
        + _navbar() + "\n" + body + "\n" + _footer(meta) + "\n</body>\n</html>"
    )

# ── Data Layer ─────────────────────────────────────────

def read_json(path, default):
    if not Path(path).exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_text(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

def load_meta():
    meta = read_json(META_PATH, {"site_name": SITE_TITLE, "contact_email": "", "categories": []})
    meta.setdefault("site_name", SITE_TITLE)
    meta.setdefault("contact_email", "")
    meta.setdefault("categories", [])
    for c in meta["categories"]:
        c.setdefault("description", "")
        c.setdefault("icon", "\U0001f4c1")
        c.setdefault("subpages", [])
        for s in c["subpages"]:
            s.setdefault("description", "")
            s.setdefault("icon", "\U0001f4c4")
    return meta

def safe_url(rel):
    return "/" + quote(rel.replace("\\", "/"), safe="/-_.()")

def fmt_size(n):
    if not n:
        return "--"
    s = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if s < 1024:
            return (str(int(s)) + " " + u) if u == "B" else ("{:.1f}".format(s) + " " + u)
        s /= 1024
    return "{:.1f}".format(s) + " TB"

def scan_files(meta):
    """Scan category directories for files, excluding generated HTML pages."""
    generated = {"index.html"}
    for c in meta["categories"]:
        generated.add("cat/" + c["slug"] + ".html")
        for s in c["subpages"]:
            generated.add(c["slug"] + "/" + s["slug"] + "/index.html")
    items = []
    for c in meta["categories"]:
        root = SITE_ROOT / c["slug"]
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(SITE_ROOT).as_posix()
            if rel in generated:
                continue
            st = p.stat()
            items.append({
                "name": rel,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    items.sort(key=lambda x: x["name"])
    return items

def write_files_json(meta):
    items = scan_files(meta)
    write_text(FILES_PATH, json.dumps(items, ensure_ascii=False, indent=2))
    return items

def group_files(meta, items):
    """Group scanned files by category and subpage."""
    grouped = {}
    for c in meta["categories"]:
        grouped[c["slug"]] = {"direct": [], "count": 0, "subpages": {}}
        for s in c["subpages"]:
            grouped[c["slug"]]["subpages"][s["slug"]] = []
    for item in items:
        parts = item["name"].split("/")
        if not parts:
            continue
        cs = parts[0]
        if cs not in grouped:
            continue
        grouped[cs]["count"] += 1
        if len(parts) >= 2 and parts[1] in grouped[cs]["subpages"]:
            e = dict(item)
            e["display_name"] = "/".join(parts[2:]) or parts[-1]
            grouped[cs]["subpages"][parts[1]].append(e)
        else:
            e = dict(item)
            e["display_name"] = "/".join(parts[1:]) or parts[-1]
            grouped[cs]["direct"].append(e)
    return grouped

# ── Page Builders ──────────────────────────────────────

def build_homepage(meta, grouped):
    """Generate index.html with hero, stats, category cards, and recent files."""
    # Category cards
    cards = []
    for c in meta["categories"]:
        cnt = grouped[c["slug"]]["count"]
        cards.append(
            '<a href="/cat/' + escape(c["slug"]) + '.html" class="cat-card">'
            '<div class="cat-icon">' + escape(c["icon"]) + '</div>'
            '<div class="cat-info"><div class="cat-name">' + escape(c["name"]) + '</div>'
            '<div class="cat-count">' + str(cnt) + " files</div></div>"
            '<span class="cat-arrow">\u2192</span></a>'
        )

    # Recent files (from study/gaokao)
    recent = []
    if "study" in grouped:
        for sp_files in grouped["study"]["subpages"].values():
            recent.extend(sp_files)
    recent.sort(key=lambda x: x.get("modified", ""), reverse=True)
    recent = recent[:8]

    recent_rows = []
    for f in recent:
        name = f.get("display_name", f.get("name", ""))
        short = name if len(name) <= 30 else name[:28] + ".."
        recent_rows.append(
            '<a href="' + safe_url(f["name"]) + '" class="file-card" target="_blank">'
            '<span class="fc-icon">PDF</span><span class="fc-info">'
            '<span class="fc-name" title="' + escape(name) + '">' + escape(short) + '</span>'
            '<span class="fc-date">' + escape(f.get("modified", "")[:10]) + '</span></span></a>'
        )

    total = sum(g["count"] for g in grouped.values())

    body = (
        '<section class="hero">'
        "<h1>Find materials <em>simpler</em></h1>"
        "<p>Gaokao past papers, study docs, work materials &mdash; clean, fast, direct download.</p>"
        '<div class="hero-actions">'
        '<a href="/cat/study.html" class="btn btn-primary">\U0001f4da Browse \u2192</a>'
        '<a href="/about.html" class="btn btn-ghost">Learn more</a>'
        "</div></section>"
        '<section class="stats">'
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">' + str(total)
        + '</span></div><div class="stat-label">Total Files</div></div>'
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">17</span></div>'
        '<div class="stat-label">Years</div></div>'
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">'
        + str(len(meta["categories"])) + '</span></div><div class="stat-label">Categories</div></div>'
        "</section>"
        '<section class="sec"><div class="sec-inner">'
        '<div class="sec-tag">Recently Updated</div>'
        '<div class="sec-title">Latest Files</div>'
        '<div class="sec-sub">Recently uploaded gaokao past papers.</div>'
        '<div class="file-grid">' + "".join(recent_rows) + "</div>"
        "</div></section>"
        '<section class="sec"><div class="sec-inner">'
        '<div class="sec-tag">Browse</div>'
        '<div class="sec-title">By Category</div>'
        '<div class="sec-sub">Choose a category to find what you need.</div>'
        '<div class="cat-grid">' + "".join(cards) + "</div>"
        "</div></section>"
    )
    write_text(SITE_ROOT / "index.html", _page(meta["site_name"] + " \u00b7 " + SITE_NAME, body, meta))

def build_category_page(meta, cat, grouped):
    """Generate cat/{slug}.html with subpage cards and direct file list."""
    # Category chips
    chips = []
    for c in meta["categories"]:
        act = " active" if c["slug"] == cat["slug"] else ""
        chips.append(
            '<a class="chip' + act + '" href="/cat/' + escape(c["slug"]) + '.html">'
            + escape(c["icon"]) + " " + escape(c["name"]) + "</a>"
        )

    # Subpage cards
    sub_cards = ""
    if cat["subpages"]:
        sc = []
        for sp in cat["subpages"]:
            cnt = len(grouped[cat["slug"]]["subpages"].get(sp["slug"], []))
            sc.append(
                '<a href="/' + escape(cat["slug"]) + "/" + escape(sp["slug"]) + '/" class="sub-card">'
                '<div class="sub-icon">' + escape(sp["icon"]) + '</div>'
                '<div class="sub-name">' + escape(sp["name"]) + '</div>'
                '<div class="sub-desc">' + escape(sp["description"]) + " \u00b7 " + str(cnt) + " files</div></a>"
            )
        sub_cards = '<div class="sub-grid">' + "".join(sc) + "</div>"

    # Direct files
    rows = []
    for item in grouped[cat["slug"]]["direct"]:
        rows.append(
            '<div class="fitem"><div class="fitem-name">'
            '<a href="' + safe_url(item["name"]) + '" target="_blank" rel="noopener">'
            + escape(item["display_name"]) + '</a></div>'
            '<div class="fitem-date">' + escape(item.get("modified", "")[:10]) + '</div>'
            '<div class="fitem-size">' + fmt_size(item["size"]) + "</div></div>"
        )
    file_html = "".join(rows) if rows else '<div class="fitem-empty">No files yet</div>'

    body = (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">Home</a><span>\u203a</span>'
        "<span>" + escape(cat["name"]) + "</span></div>"
        '<h1 class="page-title">' + escape(cat["icon"]) + " " + escape(cat["name"]) + "</h1>"
        '<div class="page-desc">' + escape(cat["description"]) + "</div>"
        '<div class="chip-nav">' + "".join(chips) + "</div></div></section>"
        '<section class="sec"><div class="sec-inner">'
        + sub_cards + '<div class="file-panel">' + file_html + "</div>"
        "</div></section>"
    )
    write_text(CATEGORY_DIR / (cat["slug"] + ".html"), _page(cat["name"] + " - " + SITE_NAME, body, meta))

def build_subpage(meta, cat, sp, sp_items):
    """Generate {category}/{subpage}/index.html with search + pagination."""
    # Build file data for embedded JSON
    fd = []
    for item in sp_items:
        fd.append({
            "n": item.get("display_name", item.get("name", "")),
            "u": safe_url(item["name"]),
            "s": fmt_size(item["size"]),
            "d": item.get("modified", "")[:10],
        })
    fj = json.dumps(fd, ensure_ascii=False)

    body = (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">Home</a><span>\u203a</span>'
        '<a href="/cat/' + escape(cat["slug"]) + '.html">' + escape(cat["name"]) + '</a>'
        "<span>\u203a</span><span>" + escape(sp["name"]) + "</span></div>"
        '<h1 class="page-title">' + escape(sp["icon"]) + " " + escape(sp["name"]) + "</h1>"
        '<div class="page-desc">' + escape(sp["description"]) + "</div>"
        '<div class="chip-nav"><a class="chip" href="/cat/' + escape(cat["slug"])
        + '.html">\u2190 Back</a></div></div></section>'
        '<section class="sec"><div class="sec-inner">'
        '<div class="toolbar"><input type="text" class="search-input" id="s" placeholder="Search files..."></div>'
        '<div class="file-panel" id="p"></div>'
        '<div class="pg-bar">'
        '<select class="pg-size-select" id="z">'
        '<option value="10">10/page</option><option value="30" selected>30/page</option>'
        '<option value="50">50/page</option></select>'
        '<div id="n"></div><span class="pg-info" id="i"></span>'
        "</div></div></section>"
        # Embedded data + ES5 search/pagination
        "<script>var F=" + fj
        + ';(function(){var a=F.slice(),s=30,c=1,p=document.getElementById("p"),'
        + 'g=document.getElementById("n"),t=document.getElementById("i"),'
        + 'q=document.getElementById("s"),z=document.getElementById("z");'
        + "function e(x){var d=document.createElement('div');"
        + "d.appendChild(document.createTextNode(x));return d.innerHTML}"
        + "function h(x){return"
        + '\'<div class=\"fitem\"><div class=\"fitem-name\"><a href=\"\'+x.u+\'\" target=\"_blank\" rel=\"noopener\">\''
        + "+e(x.n)+'</a></div><div class=\"fitem-date\">'+x.d+'</div>"
        + '<div class=\"fitem-size\">\'+x.s+\'</div></div>\'}'
        + "function r(d){var x=(c-1)*s,y=Math.min(x+s,d.length),o='';"
        + "for(var i=x;i<y;i++)o+=h(d[i]);if(!d.length)o='<div class=\"fitem-empty\">No matching files</div>';"
        + "p.innerHTML=o}"
        + "function v(tp){var tp2=Math.ceil(tp/s);if(tp2<=1){g.innerHTML='';"
        + 't.innerHTML="Total: "+tp+" files";return}c=Math.min(c,tp2);'
        + 't.innerHTML="Total: "+tp+" files \\u00b7 Page "+c+"/"+tp2;'
        + "var o='';if(c>1)o+='<span class=\"pg-btn\" id=\"pv\">\\u2039</span>';"
        + "else o+='<span class=\"pg-btn disabled\">\\u2039</span>';var ps=[];"
        + "if(tp2<=7){for(var i2=1;i2<=tp2;i2++)ps.push(i2)}else{ps.push(1);"
        + "if(c>3)ps.push('...');var x2=Math.max(2,c-1),y2=Math.min(tp2-1,c+1);"
        + "for(var i2=x2;i2<=y2;i2++)ps.push(i2);if(c<tp2-2)ps.push('...');ps.push(tp2)}"
        + "for(var i2=0;i2<ps.length;i2++){if(ps[i2]==='...')o+='<span class=\"pg-btn disabled\">\\u2026</span>';"
        + "else if(ps[i2]===c)o+='<span class=\"pg-btn active\">'+ps[i2]+'</span>';"
        + "else o+='<span class=\"pg-btn\" data-p=\"'+ps[i2]+'\">'+ps[i2]+'</span>'}"
        + "if(c<tp2)o+='<span class=\"pg-btn\" id=\"nx\">\\u203a</span>';"
        + "else o+='<span class=\"pg-btn disabled\">\\u203a</span>';g.innerHTML=o}"
        + "function u(){r(a);v(a.length)}"
        + "g.onclick=function(ev){ev=ev||window.event;var el=ev.target||ev.srcElement;"
        + "if(el.className.indexOf('pg-btn')<0||el.className.indexOf('disabled')>=0"
        + "||el.className.indexOf('active')>=0)return;"
        + "var dp=el.getAttribute('data-p');if(dp){c=parseInt(dp);u();return}"
        + "if(el.id==='pv'){c=Math.max(1,c-1);u()}"
        + "if(el.id==='nx'){c=Math.min(Math.ceil(a.length/s),c+1);u()}};"
        + "z.onchange=function(){s=parseInt(z.value);c=1;u()};"
        + "q.oninput=function(){var k=q.value.toLowerCase();"
        + "if(!k){a=F.slice();c=1;u();return}a=[];"
        + "for(var i2=0;i2<F.length;i2++)if(F[i2].n.toLowerCase().indexOf(k)>=0)a.push(F[i2]);"
        + "c=1;u()};u()})();</script>"
    )

    sp_dir = SITE_ROOT / cat["slug"] / sp["slug"]
    sp_dir.mkdir(parents=True, exist_ok=True)
    write_text(sp_dir / "index.html", _page(sp["name"] + " - " + cat["name"] + " - " + SITE_NAME, body, meta))

# ── Build Orchestrator ─────────────────────────────────

def build_all(meta=None):
    """Run full build: scan files, generate all pages. Returns stats dict."""
    meta = meta or load_meta()
    items = write_files_json(meta)
    grouped = group_files(meta, items)
    CATEGORY_DIR.mkdir(parents=True, exist_ok=True)

    build_homepage(meta, grouped)
    for c in meta["categories"]:
        (SITE_ROOT / c["slug"]).mkdir(parents=True, exist_ok=True)
        build_category_page(meta, c, grouped)
        for sp in c["subpages"]:
            build_subpage(meta, c, sp, grouped[c["slug"]]["subpages"].get(sp["slug"], []))

    return {"files": len(items), "categories": len(meta["categories"])}

# ── Validator ──────────────────────────────────────────

# Patterns that MUST NOT appear in generated HTML (WeChat/ES5 constraint)
_FORBIDDEN = [
    ("classList", "ES6 classList API"),
    ("const ", "ES6 const declaration"),
    ("let ", "ES6 let declaration"),
    ("=>", "ES6 arrow function"),
    ("fetch(", "ES6 fetch API"),
    ("addEventListener", "DOM addEventListener (use .onclick)"),
    ("var(", "CSS var() function"),
]

def validate():
    """Check all generated HTML files for ES6/CSS violations. Returns (passed, violation_count)."""
    targets = (
        [SITE_ROOT / "index.html"]
        + list((SITE_ROOT / "cat").glob("*.html"))
        + list((SITE_ROOT / "study").rglob("index.html"))
    )
    violations = 0
    for fp in targets:
        if not fp.exists():
            print("  MISSING: " + str(fp.relative_to(SITE_ROOT)))
            violations += 1
            continue
        content = fp.read_text(encoding="utf-8")
        for pattern, label in _FORBIDDEN:
            count = content.count(pattern)
            if count > 0:
                print("  FAIL: " + fp.name + " - " + str(count) + " x '" + pattern + "' (" + label + ")")
                violations += count
    if violations == 0:
        print("  PASS: zero ES6/CSS violations across " + str(len(targets)) + " pages")
    return (violations == 0), violations

# ── CLI ────────────────────────────────────────────────

def main():
    do_build = "--validate" not in sys.argv
    do_validate = "--build" not in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0

    if do_build:
        try:
            result = build_all()
            print("BUILD: " + str(result["categories"]) + " categories, " + str(result["files"]) + " files")
        except Exception as exc:
            print("BUILD ERROR: " + str(exc), file=sys.stderr)
            return 2
        print("---")

    if do_validate:
        print("VALIDATE:")
        passed, count = validate()
        if not passed:
            print("FAILED: " + str(count) + " violation(s)")
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
