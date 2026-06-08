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
SITE_NAME    = "资料栈"
SITE_TITLE   = "\u8d44\u6599\u6808"  # 资料栈

# ── CSS ────────────────────────────────────────────────
# Single source of truth for all page styles.
# Hardcoded colors (no var()), dual-theme (.theme-dark default + .theme-light overrides).
# WeChat browser (MicroMessenger 8.0.73) compatible.

CSS = (
    # ── Reset & Base ──
    "*{margin:0;padding:0;box-sizing:border-box}"
    "html{overflow-x:hidden;-webkit-tap-highlight-color:transparent}"
    "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
    "'Noto Sans SC','Microsoft YaHei',sans-serif;background:#08090A;color:#C8CDD6;"
    "line-height:1.6;min-height:100vh;-webkit-font-smoothing:antialiased;overflow-x:hidden}"
    ".theme-light body{background:#F8FAFC;color:#2D2A26}"
    "a{color:inherit;text-decoration:none;-webkit-touch-callout:none}"
    "::selection{background:rgba(59,130,246,.35);color:#fff}"
    "img{max-width:100%;height:auto}"

    # ── Navbar ──
    ".navbar{position:sticky;top:0;z-index:100;background:rgba(8,9,10,.85);"
    "border-bottom:1px solid rgba(255,255,255,.06);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}"
    ".theme-light .navbar{background:rgba(248,250,252,.85);border-color:rgba(0,0,0,.05)}"
    ".nav-inner,.wrap,.footer-inner{max-width:1200px;margin:0 auto}"
    ".nav-inner{min-height:60px;display:flex;align-items:center;justify-content:space-between;padding:0 24px}"
    ".logo{display:flex;align-items:center;gap:10px;font-size:19px;font-weight:700;color:#F4F5F6;letter-spacing:-.3px}"
    ".theme-light .logo{color:#0F172A}"
    ".logo-icon{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#F7D08A,#D9A441,#8D5A2A);"
    "display:grid;place-items:center;box-shadow:0 4px 16px rgba(217,164,65,.3)}"
    ".logo-icon svg{width:22px;height:22px}"
    ".theme-btn{width:50px;height:28px;border-radius:99px;background:rgba(255,255,255,.06);"
    "border:1px solid rgba(255,255,255,.08);position:relative;overflow:hidden;flex-shrink:0}"
    ".theme-light .theme-btn{background:rgba(0,0,0,.05);border-color:rgba(0,0,0,.08)}"
    ".theme-link{position:absolute;inset:0;display:flex;align-items:center;text-decoration:none;color:inherit;z-index:2}"
    ".to-light{justify-content:flex-start;padding-left:8px}"
    ".to-dark{justify-content:flex-end;padding-right:8px}"
    ".theme-dark .to-dark{display:none}"
    ".theme-light .to-light{display:none}"
    ".theme-knob{position:absolute;top:2px;left:2px;z-index:1;width:22px;height:22px;border-radius:50%;"
    "background:#3B82F6;pointer-events:none;transition:left .3s cubic-bezier(.4,0,.2,1);box-shadow:0 2px 8px rgba(59,130,246,.4)}"
    ".theme-light .theme-knob{left:24px;background:#F59E0B;box-shadow:0 2px 8px rgba(245,158,11,.4)}"

    # ── Hero ──
    ".hero{position:relative;padding:clamp(64px,10vw,120px) 24px clamp(48px,8vw,80px);text-align:center;"
    "background:radial-gradient(ellipse at top,rgba(59,130,246,.08),transparent 50%),"
    "linear-gradient(180deg,#0A0C10 0%,#111620 50%,#08090A 100%)}"
    ".theme-light .hero{background:radial-gradient(ellipse at top,rgba(59,130,246,.06),transparent 50%),"
    "linear-gradient(180deg,#EFF6FF 0%,#DBEAFE 50%,#F8FAFC 100%)}"
    ".hero h1{font-size:clamp(34px,7vw,68px);line-height:1.08;font-weight:800;letter-spacing:-1.4px;"
    "color:#F5F6F7;margin-bottom:20px}"
    ".theme-light .hero h1{color:#0A0F1A}"
    ".hero h1 em{font-style:normal;background:linear-gradient(135deg,#3B82F6 20%,#8B5CF6 60%,#EC4899 100%);"
    "-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}"
    ".hero p{font-size:clamp(15px,2vw,18px);color:#7A7F88;max-width:520px;margin:0 auto 40px;line-height:1.7}"
    ".theme-light .hero p{color:#5C5753}"
    ".hero-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:0}"

    # ── Buttons ──
    ".btn{display:inline-flex;align-items:center;gap:8px;padding:14px 32px;border-radius:10px;"
    "font-size:15px;font-weight:600;border:none;cursor:pointer;transition:all .3s}"
    ".btn-primary{background:#3B82F6;color:#fff;box-shadow:0 4px 20px rgba(59,130,246,.35)}"
    ".btn-primary:hover{background:#2563EB;transform:translateY(-2px);box-shadow:0 8px 28px rgba(59,130,246,.45)}"
    ".btn-ghost{background:rgba(255,255,255,.02);color:#C8CDD6;border:1px solid rgba(255,255,255,.08)}"
    ".btn-ghost:hover{background:rgba(255,255,255,.05);border-color:rgba(255,255,255,.14);transform:translateY(-1px)}"
    ".theme-light .btn-ghost{background:rgba(0,0,0,.015);border-color:rgba(0,0,0,.06);color:#2D2A26}"

    # ── Stats ──
    ".stats{display:flex;justify-content:center;gap:clamp(36px,7vw,72px);padding:0 24px 64px;flex-wrap:wrap}"
    ".stat{text-align:center}"
    ".stat-num{font-size:clamp(30px,5vw,48px);font-weight:800;color:#F5F6F7;letter-spacing:-.6px;line-height:1.1}"
    ".theme-light .stat-num{color:#0A0F1A}"
    ".stat-num-grad{background:linear-gradient(135deg,#3B82F6,#8B5CF6);-webkit-background-clip:text;"
    "-webkit-text-fill-color:transparent;background-clip:text}"
    ".stat-label{font-size:13px;color:#5E636B;font-weight:500;margin-top:8px;text-transform:uppercase;letter-spacing:.4px}"

    # ── Sections ──
    ".sec{padding:0 24px 80px}"
    ".sec-inner{max-width:1100px;margin:0 auto}"
    ".sec-tag{font-size:11px;font-weight:600;color:#3B82F6;text-transform:uppercase;letter-spacing:2.5px;margin-bottom:10px}"
    ".sec-title{font-size:clamp(24px,3.5vw,36px);font-weight:700;color:#F5F6F7;letter-spacing:-.4px;margin-bottom:12px}"
    ".theme-light .sec-title{color:#0A0F1A}"
    ".sec-sub{font-size:14px;color:#5E636B;margin-bottom:32px;max-width:500px;line-height:1.6}"

    # ── Category Cards ──
    ".cat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-bottom:16px}"
    ".cat-card{display:flex;align-items:center;gap:16px;padding:22px 26px;border-radius:14px;"
    "background:rgba(255,255,255,.015);border:1px solid rgba(255,255,255,.05);transition:all .3s}"
    ".cat-card:hover{background:rgba(255,255,255,.03);border-color:rgba(59,130,246,.25);"
    "transform:translateY(-3px);box-shadow:0 12px 32px rgba(0,0,0,.35)}"
    ".theme-light .cat-card{background:#fff;border-color:rgba(0,0,0,.05);box-shadow:0 2px 10px rgba(0,0,0,.015)}"
    ".theme-light .cat-card:hover{box-shadow:0 10px 30px rgba(0,0,0,.05);border-color:rgba(59,130,246,.2)}"
    ".cat-icon{width:48px;height:48px;border-radius:12px;display:grid;place-items:center;font-size:24px;"
    "flex-shrink:0;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.05)}"
    ".theme-light .cat-icon{background:#F1F5F9;border-color:rgba(0,0,0,.04)}"
    ".cat-info{min-width:0;flex:1}"
    ".cat-name{font-size:16px;font-weight:600;color:#F4F5F6;margin-bottom:3px}"
    ".theme-light .cat-name{color:#0A0F1A}"
    ".cat-count{font-size:12px;color:#5E636B;font-weight:500}"
    ".cat-arrow{color:#484D55;font-size:18px;flex-shrink:0;transition:all .3s;opacity:.35}"
    ".cat-card:hover .cat-arrow{transform:translateX(4px);color:#3B82F6;opacity:1}"

    # ── File Cards ──
    ".file-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:10px}"
    ".file-card{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:10px;"
    "background:rgba(255,255,255,.012);border:1px solid rgba(255,255,255,.04);transition:all .25s}"
    ".file-card:hover{background:rgba(59,130,246,.04);border-color:rgba(59,130,246,.2);transform:translateY(-2px)}"
    ".theme-light .file-card{background:#fff;border-color:rgba(0,0,0,.04);box-shadow:0 1px 6px rgba(0,0,0,.01)}"
    ".fc-icon{width:36px;height:36px;border-radius:10px;flex-shrink:0;"
    "background:linear-gradient(135deg,rgba(239,68,68,.12),rgba(239,68,68,.04));border:1px solid rgba(239,68,68,.1);"
    "display:grid;place-items:center;font-size:10px;font-weight:700;color:#EF4444}"
    ".fc-info{min-width:0}"
    ".fc-name{font-size:12px;font-weight:500;color:#C8CDD6;white-space:nowrap;overflow:hidden;"
    "text-overflow:ellipsis;display:block}"
    ".theme-light .fc-name{color:#1F2937}"
    ".fc-date{font-size:10px;color:#5E636B;margin-top:3px}"

    # ── Page Hero (category/subpage) ──
    ".page-hero{padding:36px 24px 24px;background:linear-gradient(180deg,#0A0C10 0%,#111620 50%,#08090A 100%)}"
    ".theme-light .page-hero{background:linear-gradient(180deg,#EFF6FF 0%,#DBEAFE 50%,#F8FAFC 100%)}"
    ".breadcrumbs{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:13px;color:#5E636B;margin-bottom:8px}"
    ".breadcrumbs a{color:#60A5FA}"
    ".page-title{font-size:clamp(24px,3.5vw,38px);font-weight:800;color:#F5F6F7;margin-top:8px}"
    ".theme-light .page-title{color:#0A0F1A}"
    ".page-desc{font-size:14px;color:#5E636B;margin-top:6px}"
    ".chip-nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}"
    ".chip{display:inline-block;padding:6px 14px;border-radius:99px;background:rgba(255,255,255,.03);"
    "border:1px solid rgba(255,255,255,.06);font-size:12px;font-weight:500}"
    ".chip:hover{background:rgba(59,130,246,.1);border-color:rgba(59,130,246,.25);color:#60A5FA}"
    ".chip.active{background:#3B82F6;border-color:#3B82F6;color:#fff}"
    ".theme-light .chip{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.04);color:#374151}"

    # ── Subpage Cards ──
    ".sub-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin:24px 0}"
    ".sub-card{display:block;padding:24px;border-radius:14px;background:rgba(255,255,255,.015);"
    "border:1px solid rgba(255,255,255,.04);transition:all .25s}"
    ".sub-card:hover{transform:translateY(-3px);border-color:rgba(59,130,246,.2);"
    "background:rgba(255,255,255,.025);box-shadow:0 10px 28px rgba(0,0,0,.25)}"
    ".theme-light .sub-card{background:#fff;border-color:rgba(0,0,0,.04);box-shadow:0 2px 8px rgba(0,0,0,.01)}"
    ".theme-light .sub-card:hover{box-shadow:0 10px 28px rgba(0,0,0,.04)}"
    ".sub-icon{font-size:32px;margin-bottom:10px;display:block}"
    ".sub-name{font-size:16px;font-weight:700;color:#F4F5F6}"
    ".theme-light .sub-name{color:#0A0F1A}"
    ".sub-desc{font-size:12px;color:#5E636B;margin-top:6px}"

    # ── File Panel ──
    ".file-panel{background:rgba(255,255,255,.01);border:1px solid rgba(255,255,255,.05);"
    "border-radius:14px;overflow:hidden}"
    ".theme-light .file-panel{background:#fff;border-color:rgba(0,0,0,.05)}"
    ".fitem{display:grid;grid-template-columns:minmax(0,1fr) 100px 75px;gap:10px;padding:12px 18px;"
    "border-bottom:1px solid rgba(255,255,255,.03);align-items:center}"
    ".theme-light .fitem{border-color:rgba(0,0,0,.03)}"
    ".fitem:last-child{border-bottom:none}"
    ".fitem:nth-child(odd){background:rgba(255,255,255,.008)}"
    ".theme-light .fitem:nth-child(odd){background:#F8FAFC}"
    ".fitem-name{font-size:13px;word-break:break-all}"
    ".fitem-name a:hover{color:#60A5FA}"
    ".fitem-date,.fitem-size{font-size:12px;color:#5E636B;white-space:nowrap}"
    ".fitem-empty{padding:40px 18px;text-align:center;color:#5E636B;font-size:13px}"

    # ── Search ──
    ".toolbar{margin-bottom:12px}"
    ".search-input{width:100%;padding:10px 16px;border-radius:10px;border:1px solid rgba(255,255,255,.08);"
    "background:rgba(255,255,255,.02);color:#C8CDD6;font-size:14px;outline:none}"
    ".search-input:focus{border-color:#60A5FA}"
    ".search-input::placeholder{color:#484D55}"
    ".theme-light .search-input{background:#fff;border-color:rgba(0,0,0,.08);color:#2D2A26}"

    # ── Pagination ──
    ".pg-bar{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;padding:14px 18px}"
    ".pg-size-select{padding:5px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.08);"
    "background:rgba(255,255,255,.02);color:#C8CDD6;font-size:12px;outline:none}"
    ".pg-btn{display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:32px;"
    "border-radius:8px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.015);"
    "color:#C8CDD6;font-size:13px;font-weight:500;user-select:none;cursor:pointer;-webkit-tap-highlight-color:transparent}"
    ".pg-btn:hover{background:#2563EB;border-color:#2563EB;color:#fff}"
    ".pg-btn.active{background:#3B82F6;border-color:#3B82F6;color:#fff;font-weight:600}"
    ".pg-btn.disabled{opacity:.25;cursor:default}"
    ".pg-info{font-size:12px;color:#5E636B;white-space:nowrap}"
    ".theme-light .pg-size-select,.theme-light .pg-btn{background:#fff;border-color:rgba(0,0,0,.06);color:#2D2A26}"

    # ── Footer ──
    ".footer{margin-top:40px;padding:48px 24px 28px;border-top:1px solid rgba(255,255,255,.04);"
    "color:#5E636B;font-size:12px}"
    ".theme-light .footer{border-color:rgba(0,0,0,.04);color:#5C5753}"
    ".footer-inner{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr;"
    "gap:32px;margin-bottom:28px}"
    ".footer-brand .logo{font-size:16px;margin-bottom:10px}"
    ".footer-brand p{font-size:12px;color:#5E636B;line-height:1.7;max-width:300px}"
    ".footer-col h4{font-size:11px;font-weight:600;color:#848A94;text-transform:uppercase;"
    "letter-spacing:1.5px;margin-bottom:12px}"
    ".footer-col ul{list-style:none}"
    ".footer-col li{margin-bottom:8px}"
    ".footer-col a{font-size:12px;transition:color .2s}"
    ".footer-col a:hover{color:#60A5FA}"
    ".footer-bottom{max-width:1100px;margin:0 auto;padding-top:20px;border-top:1px solid rgba(255,255,255,.03);"
    "display:flex;justify-content:center;gap:24px;flex-wrap:wrap;gap:10px;font-size:11px}"
    ".theme-light .footer-bottom{border-color:rgba(0,0,0,.03)}"
    ".footer-email{color:#3B82F6}"

    # ── Responsive ──
    "@media(max-width:768px){.nav-inner,.wrap,.footer-inner{padding:0 16px}"
    ".hero{padding:56px 20px 40px}.cat-grid,.file-grid{grid-template-columns:1fr}"
    ".fitem{grid-template-columns:minmax(0,1fr) 85px 65px;gap:6px;padding:10px 14px}"
    ".sub-grid{grid-template-columns:1fr}.footer-inner{grid-template-columns:1fr;gap:24px}}"
    "@media(max-width:480px){.nav-inner{padding:0 14px;min-height:54px}"
    ".logo{font-size:17px}.logo-icon{width:32px;height:32px}"
    ".sec{padding:0 16px 60px}.hero h1{font-size:30px;letter-spacing:-.8px}"
    ".btn{padding:12px 22px;font-size:14px}.cat-card{padding:16px 18px}"
    ".cat-icon{width:42px;height:42px;font-size:22px}"
    ".stats{gap:28px}.stat-num{font-size:26px}"
    ".fitem{grid-template-columns:1fr;gap:4px;padding:10px 12px}.fitem-date,.fitem-size{font-size:11px}"
    ".theme-btn{width:56px;height:34px}.theme-knob{width:28px;height:28px}"
    ".theme-light .theme-knob{left:24px}.to-light{padding-left:9px;font-size:16px}"
    ".to-dark{padding-right:9px;font-size:16px}.pg-btn{min-width:28px;height:28px;font-size:12px}}"
)

# A restrained editorial layer for a long-running document library.
REFINED_CSS = (
    ":root{color-scheme:dark light}"
    "body{background:#0b0d0e;color:#c9ced3;letter-spacing:0}"
    ".theme-light body{background:#f6f7f5;color:#303531}"
    ".navbar{background:rgba(11,13,14,.94);border-color:#24282a;backdrop-filter:blur(12px)}"
    ".theme-light .navbar{background:rgba(246,247,245,.94);border-color:#dfe3df}"
    ".nav-inner{min-height:64px;gap:28px}"
    ".logo{font-size:18px;letter-spacing:0}.logo-icon{width:34px;height:34px;border-radius:7px;"
    "background:#d4a84f;box-shadow:none;color:#16191a}.logo-icon svg{width:19px;height:19px}"
    ".nav-links{display:flex;align-items:center;gap:24px;margin-left:auto}"
    ".nav-links a{font-size:13px;color:#939b9f}.nav-links a:hover{color:#f2f4f3}"
    ".theme-light .nav-links a{color:#657069}.theme-light .nav-links a:hover{color:#18201b}"
    ".theme-btn{width:34px;height:34px;border-radius:7px;display:grid;place-items:center;position:relative;"
    "background:#15191b;border:1px solid #2a3032;cursor:pointer;overflow:hidden}"
    ".theme-light .theme-btn{background:#fff;border-color:#d8ddd9}"
    ".theme-link{padding:0!important;justify-content:center!important}.theme-link svg{width:16px;height:16px}"
    ".theme-knob{display:none}"
    ".hero{padding:72px 24px 46px;text-align:left;background:#0f1213;border-bottom:1px solid #202527}"
    ".theme-light .hero{background:#eef1ed;border-color:#dce1dc}"
    ".hero-inner{max-width:1100px;margin:0 auto}.hero-kicker{font-size:12px;color:#d4a84f;font-weight:700;"
    "margin-bottom:16px}.hero h1{max-width:720px;font-size:clamp(38px,5.5vw,62px);line-height:1.12;"
    "letter-spacing:0;margin-bottom:18px;font-weight:760}.hero h1 em{color:#d4a84f;background:none;"
    "-webkit-text-fill-color:currentColor}.hero p{margin:0 0 28px;max-width:680px;font-size:16px;color:#949c9f}"
    ".theme-light .hero p{color:#626b65}.hero-actions{justify-content:flex-start}"
    ".btn{border-radius:7px;padding:12px 20px;font-size:14px;transition:background .18s,border-color .18s}"
    ".btn:hover{transform:none!important;box-shadow:none!important}"
    ".btn-primary{background:#d4a84f;color:#17191a;box-shadow:none}.btn-primary:hover{background:#e0b85f}"
    ".btn-ghost{background:transparent;border-color:#33393b}.btn-icon{width:17px;height:17px}"
    ".stats{max-width:1100px;margin:0 auto;justify-content:flex-start;gap:0;padding:28px 24px 64px}"
    ".stat{text-align:left;min-width:150px;padding-right:40px;margin-right:40px;border-right:1px solid #262b2d}"
    ".stat:last-child{border-right:0}.stat-num{font-size:28px;letter-spacing:0}.stat-num-grad{background:none;"
    "-webkit-text-fill-color:currentColor;color:#edf0ee}.theme-light .stat-num-grad{color:#202720}"
    ".stat-label{text-transform:none;letter-spacing:0;margin-top:4px;color:#747c80}"
    ".sec{padding-bottom:64px}.sec-inner{max-width:1100px}.sec-tag{color:#b89143;letter-spacing:0;"
    "text-transform:none;font-size:12px}.sec-title{font-size:28px;letter-spacing:0;margin-bottom:8px}"
    ".sec-sub{margin-bottom:24px}.file-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;"
    "background:#252a2c;border:1px solid #252a2c;border-radius:7px;overflow:hidden}"
    ".file-card{border:0;border-radius:0;background:#101314;padding:15px 16px;transform:none}"
    ".file-card:hover{background:#171b1c;transform:none}.fc-icon{border-radius:5px;background:#251719;"
    "border-color:#4d272a}.fc-name{font-size:13px}.cat-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}"
    ".cat-card{border-radius:7px;padding:20px;background:#101314;border-color:#292e30;transform:none}"
    ".cat-card:hover{transform:none;box-shadow:none;background:#15191a;border-color:#4c5356}"
    ".cat-icon{width:42px;height:42px;border-radius:6px;background:#171b1c;border-color:#303638;color:#d4a84f}"
    ".cat-icon svg{width:21px;height:21px}.cat-arrow svg{width:17px;height:17px}"
    ".cat-name{font-size:15px}.page-hero{background:#0f1213;border-bottom:1px solid #202527}"
    ".theme-light .page-hero{background:#eef1ed;border-color:#dce1dc}"
    ".page-title{letter-spacing:0}.page-title-icon{display:inline-grid;place-items:center;width:30px;height:30px;"
    "vertical-align:-6px;margin-right:5px;color:#d4a84f}.page-title-icon svg{width:24px;height:24px}"
    ".chip{border-radius:6px}.chip.active{background:#d4a84f;border-color:#d4a84f;color:#17191a}"
    ".sub-card,.file-panel,.search-input{border-radius:7px}.sub-icon{color:#d4a84f}.sub-icon svg{width:28px;height:28px}"
    ".footer{background:#090b0c;border-color:#202426}.theme-light .footer{background:#eef1ed;border-color:#dce1dc}"
    ".footer-col h4{text-transform:none;letter-spacing:0}.footer-bottom{justify-content:space-between}"
    "@media(max-width:768px){.nav-links{display:none}.hero{padding:52px 20px 36px}.file-grid,.cat-grid{grid-template-columns:1fr}"
    ".stats{padding-bottom:52px}.stat{min-width:0;flex:1;padding-right:18px;margin-right:18px}.footer-bottom{justify-content:center}}"
    "@media(max-width:480px){.hero h1{font-size:34px}.hero-actions{display:grid;grid-template-columns:1fr 1fr}"
    ".btn{justify-content:center;padding:11px 12px}.stats{gap:0}.stat-num{font-size:24px}.stat-label{font-size:11px}"
    ".sec-title{font-size:25px}.theme-btn{width:34px;height:34px}.cat-card{padding:16px}}"
)

# ── SVG Icons ──────────────────────────────────────────

LOGO_SVG = (
    '<svg viewBox="0 0 24 24" role="img" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5h16v14H4z"/>'
    '<path d="M7 5.5V3h10v2.5M8 10h8M8 14h5"/></svg>'
)

LOGO_SVG_SMALL = LOGO_SVG.replace('viewBox="0 0 48 48"', 'viewBox="0 0 48 48" style="width:16px;height:16px"')

ICON_SVGS = {
    "study": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z"/></svg>',
    "history": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 21h18M5 21V9h14v12M3 9l9-6 9 6M9 13v4M15 13v4"/></svg>',
    "default": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>',
}

ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12h14M14 7l5 5-5 5"/></svg>'
SEARCH_SVG = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>'
SUN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
MOON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 15.5A8 8 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5z"/></svg>'

def _category_icon(slug):
    return ICON_SVGS.get(slug, ICON_SVGS["default"])

# ── HTML Templates ─────────────────────────────────────

def _navbar():
    """Return the shared navigation bar HTML."""
    return (
        '<nav class="navbar"><div class="nav-inner">'
        '<a href="/" class="logo"><span class="logo-icon" aria-hidden="true">'
        + LOGO_SVG + '</span><span>' + SITE_TITLE + '</span></a>'
        '<div class="nav-links"><a href="/">首页</a><a href="/cat/study.html">资料库</a><a href="/about.html">关于</a></div>'
        '<button class="theme-btn" id="themeBtn" type="button" aria-label="切换明暗主题">'
        '<span class="theme-link to-light">' + SUN_SVG + '</span>'
        '<span class="theme-link to-dark">' + MOON_SVG + '</span>'
        '<span class="theme-knob" aria-hidden="true"></span></button>'
        '</div></nav>'
    )
def _footer(meta):
    """Return the shared footer HTML."""
    cat_links = "".join(
        '<li><a href="/cat/' + escape(c["slug"]) + '.html">' + escape(c["name"]) + "</a></li>"
        for c in meta["categories"]
    )
    return (
        '<footer class="footer"><div class="footer-inner">'
        '<div class="footer-brand"><div class="logo"><span class="logo-icon">'
        + LOGO_SVG_SMALL + "</span>" + escape(meta["site_name"])
        + '</div><p>安全、高效、便捷。高考试题根据著作权法第五条属于公有领域。</p></div>'
        '<div class="footer-col"><h4>资源</h4><ul><li><a href="/">首页</a></li>'
        + cat_links + '<li><a href="/about.html">关于</a></li></ul></div>'
        '<div class="footer-col"><h4>站点信息</h4><ul>'
        '<li><a href="/about.html" class="footer-email">内容与版权说明</a></li>'
        '<li><a href="/privacy.html">隐私政策</a></li><li><a href="/terms.html">服务条款</a></li>'
        '</ul></div></div>'
        '<div class="footer-bottom"><span>&copy; 2026 ' + escape(meta["site_name"]) + '</span><span><a href="https://beian.miit.gov.cn" target="_blank" rel="noopener">赣ICP备2026012339号-1</a></span></div></footer>'
    )

def _page(title, body, meta):
    """Wrap body in full HTML document with CSS, navbar, and footer."""
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN" class="<!--# if expr=\"$cookie_theme = light\" -->theme-light<!--# else -->theme-dark<!--# endif -->">\n'
        '<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>" + escape(title) + "</title>\n"
        '<link rel="icon" href="/favicon.ico">\n<meta name="description" content="' + escape(title) + '">\n<style>\n' + CSS + REFINED_CSS + "\n</style>\n</head>\n<body>\n"
        + _navbar() + "\n" + body + "\n" + _footer(meta) + "\n<script>(function(){var h=document.documentElement;var b=document.getElementById(\"themeBtn\");b.onclick=function(){var dark=h.className.indexOf(\"theme-dark\")!==-1;h.className=dark?\"theme-light\":\"theme-dark\";document.cookie=\"theme=\"+(dark?\"light\":\"dark\")+\";path=/;max-age=31536000;SameSite=Lax\";};})();</script>\n</body>\n</html>"
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
        if cnt == 0:
            continue
        cards.append(
            '<a href="/cat/' + escape(c["slug"]) + '.html" class="cat-card">'
            '<div class="cat-icon" aria-hidden="true">' + _category_icon(c["slug"]) + '</div>'
            '<div class="cat-info"><div class="cat-name">' + escape(c["name"]) + '</div>'
            '<div class="cat-count">' + str(cnt) + " 份资料</div></div>"
            '<span class="cat-arrow" aria-hidden="true">' + ARROW_SVG + '</span></a>'
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
        '<div class="hero-inner"><div class="hero-kicker">中高考真题资料库</div>'
        "<h1>历年真题，<em>按年份与科目整理</em></h1>"
        "<p>收录各地区中高考空白试卷，保留原始 PDF，打开即可预览或下载。</p>"
        '<div class="hero-actions">'
        '<a href="/cat/study.html" class="btn btn-primary">' + SEARCH_SVG + '进入资料库</a>'
        '<a href="/about.html" class="btn btn-ghost">关于本站</a>'
        "</div></div></section>"
        '<section class="stats">'
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">' + str(total)
        + '</span></div><div class="stat-label">份可用资料</div></div>'
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">17</span></div>'
        '<div class="stat-label">个年份跨度</div></div>'
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">'
        + str(len(cards)) + '</span></div><div class="stat-label">个有效分类</div></div>'
        "</section>"
        '<section class="sec"><div class="sec-inner">'
        '<div class="sec-tag">本周整理</div>'
        '<div class="sec-title">最近收录</div>'
        '<div class="sec-sub">最新归档的真题试卷，按上传时间排列。</div>'
        '<div class="file-grid">' + "".join(recent_rows) + "</div>"
        "</div></section>"
        '<section class="sec"><div class="sec-inner">'
        '<div class="sec-tag">资料导航</div>'
        '<div class="sec-title">按用途浏览</div>'
        '<div class="sec-sub">只展示已有内容的分类，减少无效入口。</div>'
        '<div class="cat-grid">' + "".join(cards) + "</div>"
        "</div></section>"
    )
    write_text(SITE_ROOT / "index.html", _page(meta["site_name"] + " - 中高考真题空白卷免费下载", body, meta))

def build_category_page(meta, cat, grouped):
    """Generate cat/{slug}.html with subpage cards and direct file list."""
    # Category chips
    chips = []
    for c in meta["categories"]:
        act = " active" if c["slug"] == cat["slug"] else ""
        chips.append(
            '<a class="chip' + act + '" href="/cat/' + escape(c["slug"]) + '.html">'
            + escape(c["name"]) + "</a>"
        )

    # Subpage cards
    sub_cards = ""
    if cat["subpages"]:
        sc = []
        for sp in cat["subpages"]:
            cnt = len(grouped[cat["slug"]]["subpages"].get(sp["slug"], []))
            sc.append(
                '<a href="/' + escape(cat["slug"]) + "/" + escape(sp["slug"]) + '/" class="sub-card">'
                '<div class="sub-icon" aria-hidden="true">' + _category_icon(cat["slug"]) + '</div>'
                '<div class="sub-name">' + escape(sp["name"]) + '</div>'
                '<div class="sub-desc">' + escape(sp["description"]) + " \u00b7 " + str(cnt) + " 个文件</div></a>"
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
    file_html = "".join(rows) if rows else '<div class="fitem-empty">暂无文件</div>'

    body = (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">首页</a><span>\u203a</span>'
        "<span>" + escape(cat["name"]) + "</span></div>"
        '<h1 class="page-title"><span class="page-title-icon">' + _category_icon(cat["slug"]) + '</span>' + escape(cat["name"]) + "</h1>"
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
        '<div class="breadcrumbs"><a href="/">首页</a><span>\u203a</span>'
        '<a href="/cat/' + escape(cat["slug"]) + '.html">' + escape(cat["name"]) + '</a>'
        "<span>\u203a</span><span>" + escape(sp["name"]) + "</span></div>"
        '<h1 class="page-title"><span class="page-title-icon">' + _category_icon(cat["slug"]) + '</span>' + escape(sp["name"]) + "</h1>"
        '<div class="page-desc">' + escape(sp["description"]) + "</div>"
        '<div class="chip-nav"><a class="chip" href="/cat/' + escape(cat["slug"])
        + '.html">\u2190 返回</a></div></div></section>'
        '<section class="sec"><div class="sec-inner">'
        '<div class="toolbar"><input type="text" class="search-input" id="s" placeholder="搜索文件..."></div>'
        '<div class="file-panel" id="p"></div>'
        '<div class="pg-bar">'
        '<select class="pg-size-select" id="z">'
        '<option value="10">10条/页</option><option value="30" selected>30条/页</option>'
        '<option value="50">50条/页</option></select>'
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
        + "for(var i=x;i<y;i++)o+=h(d[i]);if(!d.length)o='<div class=\"fitem-empty\">没有匹配的文件</div>';"
        + "p.innerHTML=o}"
        + "function v(tp){var tp2=Math.ceil(tp/s);if(tp2<=1){g.innerHTML='';"
        + 't.innerHTML="共 "+tp+" 个文件";return}c=Math.min(c,tp2);'
        + 't.innerHTML="共 "+tp+" 个文件 · 第 "+c+"/"+tp2+" 页";'
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
