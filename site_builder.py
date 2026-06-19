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
BAIDU_AD_CODE_ENV = "SITEOPS_BAIDU_AD_CODE"
BAIDU_UNION_VERIFY = "414add309e293597a16a64f9270decc0"

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
    ".theme-light body{background:#edf4fb;color:#253041}"
    "a{color:inherit;text-decoration:none;-webkit-touch-callout:none}"
    "::selection{background:rgba(59,130,246,.35);color:#fff}"
    "img{max-width:100%;height:auto}"

    # ── Navbar ──
    ".navbar{position:sticky;top:0;z-index:100;background:rgba(8,9,10,.85);"
    "border-bottom:1px solid rgba(255,255,255,.06);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}"
    ".theme-light .navbar{background:rgba(237,244,251,.85);border-color:rgba(0,0,0,.05)}"
    ".nav-inner,.wrap,.footer-inner{max-width:1200px;margin:0 auto}"
    ".nav-inner{min-height:60px;display:flex;align-items:center;justify-content:space-between;padding:0 24px}"
    ".logo{display:flex;align-items:center;gap:10px;font-size:19px;font-weight:700;color:#F4F5F6;letter-spacing:-.3px}"
    ".theme-light .logo{color:#0F172A}"
    ".logo-icon{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#F7D08A,#D9A441,#8D5A2A);"
    "display:grid;place-items:center;box-shadow:0 4px 16px rgba(217,164,65,.3)}"
    ".logo-icon svg{width:22px;height:22px}"
    ".theme-btn{width:50px;height:28px;border-radius:99px;background:rgba(247,208,138,.10);"
    "border:1px solid rgba(247,208,138,.24);position:relative;overflow:hidden;flex-shrink:0}"
    ".theme-light .theme-btn{background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.16)}"
    ".theme-link{position:absolute;inset:0;display:flex;align-items:center;text-decoration:none;z-index:2}"
    ".theme-dark .theme-link{color:#F7D08A}"
    ".theme-light .theme-link{color:#2563EB}"
    ".to-light{justify-content:flex-start;padding-left:8px}"
    ".to-dark{justify-content:flex-end;padding-right:8px}"
    ".theme-dark .to-dark{display:none}"
    ".theme-light .to-light{display:none}"
    ".theme-knob{position:absolute;top:2px;left:2px;z-index:1;width:22px;height:22px;border-radius:50%;"
    "background:#3B82F6;pointer-events:none;transition:left .3s cubic-bezier(.4,0,.2,1);box-shadow:0 2px 8px rgba(59,130,246,.32)}"
    ".theme-light .theme-knob{left:24px;background:#F59E0B;box-shadow:0 2px 8px rgba(245,158,11,.28)}"

    # ── Hero ──
    ".hero{position:relative;padding:clamp(64px,10vw,120px) 24px clamp(48px,8vw,80px);text-align:center;"
    "background:radial-gradient(ellipse at top,rgba(59,130,246,.08),transparent 50%),"
    "linear-gradient(180deg,#0A0C10 0%,#111620 50%,#08090A 100%)}"
    ".theme-light .hero{background:radial-gradient(ellipse at top,rgba(59,130,246,.08),transparent 50%),"
    "linear-gradient(180deg,#eef5ff 0%,#dbeafe 50%,#edf4fb 100%)}"
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
    ".theme-light .cat-card{background:#f9fcff;border-color:rgba(0,0,0,.05);box-shadow:0 2px 10px rgba(0,0,0,.015)}"
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
    ".theme-light .file-card{background:#f9fcff;border-color:rgba(0,0,0,.04);box-shadow:0 1px 6px rgba(0,0,0,.01)}"
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
    ".theme-light .page-hero{background:linear-gradient(180deg,#eef5ff 0%,#dbeafe 50%,#edf4fb 100%)}"
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
    ".theme-light .sub-card{background:#f9fcff;border-color:rgba(0,0,0,.04);box-shadow:0 2px 8px rgba(0,0,0,.01)}"
    ".theme-light .sub-card:hover{box-shadow:0 10px 28px rgba(0,0,0,.04)}"
    ".sub-icon{font-size:32px;margin-bottom:10px;display:block}"
    ".sub-name{font-size:16px;font-weight:700;color:#F4F5F6}"
    ".theme-light .sub-name{color:#0A0F1A}"
    ".sub-desc{font-size:12px;color:#5E636B;margin-top:6px}"

    # ── File Panel ──
    ".file-panel{background:rgba(255,255,255,.01);border:1px solid rgba(255,255,255,.05);"
    "border-radius:14px;overflow:hidden}"
    ".theme-light .file-panel{background:#f9fcff;border-color:rgba(0,0,0,.05)}"
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
    ".theme-light .search-input{background:#f9fcff;border-color:rgba(0,0,0,.08);color:#2D2A26}"

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
    ".theme-light .pg-size-select,.theme-light .pg-btn{background:#f9fcff;border-color:rgba(0,0,0,.06);color:#2D2A26}"

    # ── Footer ──
    ".footer{margin-top:40px;padding:48px 24px 28px;border-top:1px solid rgba(255,255,255,.04);"
    "color:#5E636B;font-size:12px}"
    ".theme-light .footer{border-color:rgba(0,0,0,.04);color:#52606d}"
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
    ".beian-link{display:inline-flex;align-items:center;gap:6px;color:#7AA7FF}"
    ".beian-link:hover{color:#60A5FA}"
    ".beian-icon{width:16px;height:16px;display:block;flex-shrink:0}"
    ".footer-email{color:#3B82F6}"
    ".ad-slot{margin:16px 0;padding:14px 16px;border-radius:10px;border:1px dashed rgba(59,130,246,.28);background:rgba(59,130,246,.04)}"
    ".theme-light .ad-slot{background:#F8FBFF;border-color:rgba(59,130,246,.18)}"
    ".ad-label{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#7dd3fc;margin-bottom:8px}"
    ".theme-light .ad-label{color:#2563eb}"
    ".ad-placeholder{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}"
    ".ad-placeholder strong{font-size:14px;color:#edf0ee}"
    ".theme-light .ad-placeholder strong{color:#172033}"
    ".ad-placeholder span{font-size:12px;color:#9fb0c4;line-height:1.6}"
    ".theme-light .ad-placeholder span{color:#5f6874}"

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
    ".theme-light body{background:#edf4fb;color:#253041}"
    ".navbar{background:rgba(11,13,14,.94);border-color:#24282a;backdrop-filter:blur(12px)}"
    ".theme-light .navbar{background:rgba(237,244,251,.94);border-color:#d9e3ee}"
    ".nav-inner{min-height:64px;gap:28px}"
    ".logo{font-size:18px;letter-spacing:0}.logo-icon{width:34px;height:34px;border-radius:7px;"
    "background:#d4a84f;box-shadow:none;color:#16191a}.logo-icon svg{width:19px;height:19px}"
    ".nav-links{display:flex;align-items:center;gap:24px;margin-left:auto}"
    ".nav-links a{font-size:13px;color:#939b9f}.nav-links a:hover{color:#f2f4f3}"
    ".theme-light .nav-links a{color:#657069}.theme-light .nav-links a:hover{color:#18201b}"
    ".theme-btn{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;position:relative;"
    "background:rgba(247,208,138,.10);border:1px solid rgba(247,208,138,.24);cursor:pointer;overflow:hidden}"
    ".theme-light .theme-btn{background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.16)}"
    ".theme-link{padding:0!important;justify-content:center!important}.theme-link svg{width:16px;height:16px}"
    ".theme-knob{display:none}"
    ".hero{position:relative;overflow:hidden;padding:72px 24px 46px;text-align:left;background:#0b0f15;border-bottom:1px solid #202527}"
    ".hero:before{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(125,211,252,.09) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,.08) 1px,transparent 1px);background-size:42px 42px;opacity:.18;pointer-events:none}"
    ".hero:after{content:'';position:absolute;left:0;right:0;bottom:0;height:1px;background:linear-gradient(90deg,transparent,rgba(125,211,252,.65),transparent);opacity:.7;pointer-events:none}"
    ".theme-light .hero{background:linear-gradient(180deg,#eef5ff 0%,#e4effc 100%);border-color:#dce6f3}"
    ".hero-inner{position:relative;z-index:1;max-width:1100px;margin:0 auto}.hero-kicker{font-size:12px;color:#7dd3fc;font-weight:700;"
    "margin-bottom:16px;letter-spacing:2px;text-transform:uppercase}.hero h1{max-width:900px;font-size:clamp(38px,5vw,58px);line-height:1.12;"
    "letter-spacing:0;margin-bottom:18px;font-weight:760}.hero h1 em{color:#7dd3fc;background:none;"
    "-webkit-text-fill-color:currentColor}.hero p{margin:0 0 28px;max-width:680px;font-size:16px;color:#93a4b8}"
    ".theme-light .hero p{color:#5f6874}.hero-actions{justify-content:flex-start}"
    ".btn{border-radius:8px;padding:12px 20px;font-size:14px;transition:background .18s,border-color .18s,transform .18s}"
    ".btn:hover{transform:none!important;box-shadow:none!important}"
    ".btn-primary{background:linear-gradient(135deg,#22d3ee,#3b82f6);color:#061019;box-shadow:none}.btn-primary:hover{background:linear-gradient(135deg,#67e8f9,#60a5fa)}"
    ".btn-ghost{background:transparent;border-color:#2d3748;color:#d7e3f1}.btn-icon{width:17px;height:17px}"
    ".commercial{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}"
    ".offer-card{padding:22px 20px;border:1px solid rgba(125,211,252,.18);border-radius:10px;background:linear-gradient(180deg,rgba(7,16,28,.98),rgba(12,18,26,.98));box-shadow:0 20px 40px rgba(0,0,0,.22)}"
    ".theme-light .offer-card{background:linear-gradient(180deg,#f9fcff,#eef5ff);border-color:rgba(59,130,246,.12)}"
    ".offer-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}"
    ".offer-kicker{font-size:12px;color:#9fe7ff;text-transform:none;letter-spacing:0;font-weight:700}"
    ".offer-title{font-size:18px;font-weight:700;color:#edf0ee;margin-bottom:8px}"
    ".theme-light .offer-title{color:#172033}"
    ".offer-desc{font-size:14px;line-height:1.7;color:#9fb0c4;margin-bottom:14px}"
    ".theme-light .offer-desc{color:#5f6874}"
    ".offer-list{list-style:none;margin-bottom:16px}.offer-list li{position:relative;padding-left:14px;margin-bottom:8px;color:#c9d7e8;font-size:13px}"
    ".theme-light .offer-list li{color:#2e3745}.offer-list li:before{content:'•';position:absolute;left:0;top:0;color:#7dd3fc}"
    ".offer-actions{display:flex;gap:10px;flex-wrap:wrap}.offer-actions .btn{padding:10px 16px;font-size:13px}"
    ".service-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}"
    ".service-card{padding:22px 20px;border:1px solid rgba(125,211,252,.14);border-radius:10px;background:linear-gradient(180deg,rgba(9,15,23,.96),rgba(10,14,22,.96));box-shadow:0 16px 30px rgba(0,0,0,.18)}"
    ".theme-light .service-card{background:linear-gradient(180deg,#f9fcff,#eef5ff);border-color:rgba(59,130,246,.12)}"
    ".service-card h3{font-size:16px;font-weight:700;color:#edf0ee;margin-bottom:8px}"
    ".theme-light .service-card h3{color:#172033}"
    ".service-card p{font-size:14px;line-height:1.7;color:#9fb0c4;margin-bottom:12px}"
    ".theme-light .service-card p{color:#5f6874}"
    ".service-metrics{display:flex;flex-wrap:wrap;gap:8px}.metric-pill{padding:6px 10px;border-radius:999px;background:rgba(20,28,40,.9);border:1px solid rgba(125,211,252,.16);font-size:12px;color:#d3e7ff}"
    ".theme-light .metric-pill{background:#f4f8ff;border-color:rgba(59,130,246,.14);color:#415069}"
    ".cta-band{padding:24px 20px;border-radius:10px;background:linear-gradient(135deg,rgba(10,16,24,.96),rgba(9,22,36,.96));border:1px solid rgba(125,211,252,.2);display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:12px;box-shadow:0 20px 44px rgba(0,0,0,.2)}"
    ".theme-light .cta-band{background:linear-gradient(135deg,#f9fcff,#eef5ff);border-color:rgba(59,130,246,.12)}"
    ".cta-band strong{display:block;font-size:18px;color:#edf0ee;margin-bottom:4px}"
    ".theme-light .cta-band strong{color:#172033}"
    ".cta-band span{font-size:13px;color:#9fb0c4;line-height:1.6}"
    ".theme-light .cta-band span{color:#5f6874}"
    ".page-note{margin-top:12px;font-size:12px;color:#7b8ca1;line-height:1.7}"
    ".editorial-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}"
    ".editorial-card{padding:22px 20px;border:1px solid #292f32;border-radius:8px;background:#101415}"
    ".theme-light .editorial-card{background:#f9fcff;border-color:#dce6f3}"
    ".editorial-index{font-size:12px;font-weight:700;color:#7dd3fc;margin-bottom:20px}"
    ".editorial-card h3{font-size:17px;color:#edf0ee;margin-bottom:8px}"
    ".theme-light .editorial-card h3{color:#17201b}"
    ".editorial-card p{font-size:14px;line-height:1.75;color:#96a4ad}"
    ".theme-light .editorial-card p{color:#5f6863}"
    ".guide-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:#292f32;"
    "border:1px solid #292f32;border-radius:8px;overflow:hidden}"
    ".guide-item{padding:20px;background:#101415}"
    ".theme-light .guide-item{background:#f9fcff}"
    ".guide-item strong{display:block;color:#edf0ee;font-size:15px;margin-bottom:6px}"
    ".theme-light .guide-item strong{color:#17201b}"
    ".guide-item span{display:block;color:#93a0a8;font-size:13px;line-height:1.7}"
    ".theme-light .guide-item span{color:#606963}"
    ".faq-list{border-top:1px solid #2a3032}"
    ".faq-item{display:grid;grid-template-columns:minmax(180px,.7fr) minmax(0,1.3fr);gap:28px;"
    "padding:20px 0;border-bottom:1px solid #2a3032}"
    ".theme-light .faq-list,.theme-light .faq-item{border-color:#dce6f3}"
    ".faq-item strong{font-size:14px;color:#e7ece9}"
    ".theme-light .faq-item strong{color:#18201b}"
    ".faq-item p{font-size:13px;line-height:1.75;color:#909da5}"
    ".theme-light .faq-item p{color:#626b65}"
    ".category-note{margin:0 0 18px;padding:16px 18px;border-left:3px solid #d4a84f;background:#111617;"
    "color:#a8b2b8;font-size:13px;line-height:1.75}"
    ".theme-light .category-note{background:#f9fcff;color:#5b6878}"
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
    ".file-card,.cat-card,.sub-card{-webkit-tap-highlight-color:transparent;outline:none}"
    ".file-card:link,.file-card:visited,.cat-card:link,.cat-card:visited,.sub-card:link,.sub-card:visited{color:inherit}"
    ".theme-dark .file-card:focus,.theme-dark .file-card:active,.theme-dark .cat-card:focus,.theme-dark .cat-card:active,.theme-dark .sub-card:focus,.theme-dark .sub-card:active{background:#101314!important;color:#c9ced3!important;border-color:rgba(56,189,248,.55)!important}"
    ".theme-light .file-card,.theme-light .file-card:hover,.theme-light .file-card:focus,.theme-light .file-card:active{background:#f9fcff!important;color:#1f2937!important;border-color:rgba(56,189,248,.28)!important}"
    ".theme-light .cat-card,.theme-light .cat-card:hover,.theme-light .cat-card:focus,.theme-light .cat-card:active{background:#f9fcff!important;color:#17201b!important;border-color:rgba(56,189,248,.28)!important}"
    ".theme-light .sub-card,.theme-light .sub-card:hover,.theme-light .sub-card:focus,.theme-light .sub-card:active{background:#f9fcff!important;color:#17201b!important;border-color:rgba(56,189,248,.28)!important}"
    ".file-card:focus-visible,.cat-card:focus-visible,.sub-card:focus-visible{box-shadow:0 0 0 2px rgba(56,189,248,.45),0 0 0 6px rgba(56,189,248,.12)!important;outline:none!important}"
    ".cat-icon{width:42px;height:42px;border-radius:6px;background:#171b1c;border-color:#303638;color:#d4a84f}"
    ".cat-icon svg{width:21px;height:21px}.cat-arrow svg{width:17px;height:17px}"
    ".cat-name{font-size:15px}.page-hero{background:#0f1213;border-bottom:1px solid #202527}"
    ".theme-light .page-hero{background:linear-gradient(180deg,#eef5ff 0%,#e8f0fa 100%);border-color:#dce6f3}"
    ".page-title{letter-spacing:0}.page-title-icon{display:inline-grid;place-items:center;width:30px;height:30px;"
    "vertical-align:-6px;margin-right:5px;color:#d4a84f}.page-title-icon svg{width:24px;height:24px}"
    ".chip{border-radius:6px}.chip.active{background:#d4a84f;border-color:#d4a84f;color:#17191a}"
    ".sub-card,.file-panel,.search-input{border-radius:7px}.sub-icon{color:#d4a84f}.sub-icon svg{width:28px;height:28px}"
    ".footer{background:#090b0c;border-color:#202426}.theme-light .footer{background:#edf4fb;border-color:#dce6f3}"
    ".footer-col h4{text-transform:none;letter-spacing:0}.footer-bottom{justify-content:space-between}.beian-link{display:inline-flex;align-items:center;gap:6px;color:#7AA7FF}.beian-link:hover{color:#60A5FA}.beian-icon{width:16px;height:16px;display:block;flex-shrink:0}"
    "@media(max-width:768px){.nav-links{display:none}.hero{padding:52px 20px 36px}.file-grid,.cat-grid,.commercial,.service-grid,.editorial-grid,.guide-list{grid-template-columns:1fr}.faq-item{grid-template-columns:1fr;gap:8px}.cta-band{flex-direction:column;align-items:flex-start}"
    ".stats{padding-bottom:52px}.stat{min-width:0;flex:1;padding-right:18px;margin-right:18px}.footer-bottom{justify-content:center}}"
    "@media(max-width:480px){.hero-inner{width:100%;min-width:0}.hero h1{font-size:34px;max-width:100%;overflow-wrap:anywhere}"
    ".hero p{max-width:100%;overflow-wrap:anywhere}.hero-actions{display:grid;width:100%;grid-template-columns:minmax(0,1fr)}"
    ".btn{justify-content:center;padding:11px 12px}.stats{gap:0}.stat-num{font-size:24px}.stat-label{font-size:11px}"
    ".sec-title{font-size:25px}.theme-btn{width:34px;height:34px}.cat-card{padding:16px}}"
)

# ── SVG Icons ──────────────────────────────────────────

LOGO_SVG = (
    '<svg viewBox="0 0 24 24" role="img" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5h16v14H4z"/>'
    '<path d="M7 5.5V3h10v2.5M8 10h8M8 14h5"/></svg>'
)

LOGO_SVG_SMALL = LOGO_SVG.replace('viewBox="0 0 24 24"', 'viewBox="0 0 24 24" style="width:16px;height:16px"')

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

def _ad_slot(placement, note):
    """Render a flexible ad slot. When SITEOPS_BAIDU_AD_CODE is set, emit it raw."""
    raw = os.environ.get(BAIDU_AD_CODE_ENV, "").strip()
    if raw:
        return (
            '<div class="ad-slot ad-slot-' + escape(placement) + '">'
            '<div class="ad-label">Baidu Ad</div>'
            + raw +
            "</div>"
        )
    return ""
def _navbar(show_theme_toggle=False):
    """Return the shared navigation bar HTML."""
    theme_toggle = ""
    if show_theme_toggle:
        theme_toggle = (
            '<button class="theme-btn" id="themeBtn" type="button" aria-label="切换明暗主题">'
            '<span class="theme-link to-light">' + SUN_SVG + '</span>'
            '<span class="theme-link to-dark">' + MOON_SVG + '</span>'
            '<span class="theme-knob" aria-hidden="true"></span></button>'
        )
    return (
        '<nav class="navbar"><div class="nav-inner">'
        '<a href="/" class="logo"><span class="logo-icon" aria-hidden="true">'
        + LOGO_SVG
        + '</span><span>' + SITE_TITLE + '</span></a>'
        + '<div class="nav-links"><a href="/">首页</a><a href="/cat/study.html">资料库</a><a href="/about.html">关于</a></div>'
        + theme_toggle
        + '</div></nav>'
    )
def _footer(meta):
    """Return the shared footer HTML."""
    cat_links = "".join(
        '<li><a href="/cat/' + escape(c["slug"]) + '.html">' + escape(c["name"]) + "</a></li>"
        for c in meta["categories"]
        if c.get("_count", 1) > 0
    )
    email_li = ""
    if meta.get("contact_email"):
        email = escape(meta["contact_email"])
        email_li = '<li><a href="mailto:' + email + '" class="footer-email">' + email + '</a></li>'
    return (
        '<footer class="footer"><div class="footer-inner">'
        '<div class="footer-brand"><div class="logo"><span class="logo-icon">'
        + LOGO_SVG_SMALL + "</span>" + escape(meta["site_name"])
        + '</div><p>安全、高效、便捷。资料按主题与用途统一归档。</p></div>'
        '<div class="footer-col"><h4>资源</h4><ul><li><a href="/">首页</a></li>'
        + cat_links + '<li><a href="/about.html">关于</a></li></ul></div>'
        '<div class="footer-col"><h4>站点信息</h4><ul>'
        + email_li
        + '<li><a href="/about.html" class="footer-email">内容与版权说明</a></li>'
        + '<li><a href="/privacy.html">隐私政策</a></li><li><a href="/terms.html">服务条款</a></li>'
        '</ul></div></div>'
        '<div class="footer-bottom"><span>&copy; 2026 ' + escape(meta["site_name"]) + '</span><span><a href="https://beian.miit.gov.cn" target="_blank" rel="noopener">赣ICP备2026012339号-1</a></span><span><a class="beian-link" href="https://beian.mps.gov.cn/#/query/webSearch?code=36102202000166" rel="noreferrer noopener" target="_blank"><img src="/beian-icon.png" alt="公安备案图标" class="beian-icon">赣公网安备36102202000166号</a></span></div></footer>'
    )

def _page(title, body, meta, show_theme_toggle=False):
    """Wrap body in full HTML document with CSS, navbar, and footer."""
    head_theme_script = """<script>(function(){function c(n){var m=document.cookie.match(new RegExp("(?:^|; )"+n.replace(/([.$?*|{}()\[\]\\/\+^])/g,"\\$1")+"=([^;]*)"));return m?decodeURIComponent(m[1]):"";}function q(){try{return new URL(window.location.href).searchParams.get("theme")||"";}catch(e){return "";}}function w(t){try{var u=new URL(window.location.href);u.searchParams.set("theme",t);history.replaceState(null,"",u);}catch(e){}document.querySelectorAll("a[href]").forEach(function(a){try{var u=new URL(a.getAttribute("href"),window.location.origin);if(u.origin===window.location.origin&&u.pathname.charAt(0)==="/"){u.searchParams.set("theme",t);a.setAttribute("href",u.pathname+u.search+u.hash);}}catch(e){}});}function s(t){var h=document.documentElement;h.className=t==="light"?"theme-light":"theme-dark";try{localStorage.setItem("theme",t);}catch(e){}document.cookie="theme="+t+";path=/;max-age=31536000;SameSite=Lax";w(t);}var h=document.documentElement;var t=q();try{t=t||localStorage.getItem("theme")||c("theme")||"dark";}catch(e){t=t||c("theme")||"dark";}s(t);window.addEventListener("storage",function(e){if(e.key==="theme"&&e.newValue){s(e.newValue);}});window.addEventListener("pageshow",function(){var v=q();try{v=v||localStorage.getItem("theme")||c("theme")||"dark";}catch(e){v=v||c("theme")||"dark";}h.className=v==="light"?"theme-light":"theme-dark";w(v);});window.__setSiteTheme=s;})();</script>"""
    footer_theme_script = """<script>(function(){var h=document.documentElement;var b=document.getElementById("themeBtn");if(!b)return;b.onclick=function(){var dark=h.className.indexOf("theme-dark")!==-1;var next=dark?"light":"dark";if(window.__setSiteTheme){window.__setSiteTheme(next);}else{h.className=dark?"theme-light":"theme-dark";try{localStorage.setItem("theme",next);}catch(e){}document.cookie="theme="+next+";path=/;max-age=31536000;SameSite=Lax";try{var u=new URL(window.location.href);u.searchParams.set("theme",next);history.replaceState(null,"",u);}catch(e){}}};})();</script>"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="theme-dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<link rel="icon" href="/favicon.ico">
<meta name="description" content="{escape(title)}">
<meta name="baidu_union_verify" content="{escape(BAIDU_UNION_VERIFY)}">
{head_theme_script}
<style>
{CSS}
{REFINED_CSS}
</style>
</head>
<body>
{_navbar(show_theme_toggle=show_theme_toggle)}
{body}
{_footer(meta)}
{footer_theme_script}
</body>
</html>"""

def _render_editorial_grid(items):
    return '<div class="editorial-grid">' + "".join(
        '<div class="editorial-card"><div class="editorial-index">' + escape(item["index"]) + '</div>'
        '<h3>' + escape(item["title"]) + '</h3><p>' + escape(item["body"]) + '</p></div>'
        for item in items
    ) + "</div>"

def _render_guide_list(items):
    return '<div class="guide-list">' + "".join(
        '<div class="guide-item"><strong>' + escape(item["title"]) + '</strong>'
        '<span>' + escape(item["body"]) + '</span></div>'
        for item in items
    ) + "</div>"

def _render_faq_list(items):
    return '<div class="faq-list">' + "".join(
        '<div class="faq-item"><strong>' + escape(item["q"]) + '</strong>'
        '<p>' + escape(item["a"]) + '</p></div>'
        for item in items
    ) + "</div>"

def _content_pack(kind):
    packs = {
        "home": {
            "tag": "热门搜索",
            "title": "最容易被搜到的实用资料",
            "sub": "围绕简历、办公、学习和常用工具整理的入口，方便用户直接找到高频需求。",
            "cards": [
                {"index": "01", "title": "简历模板", "body": "适合找工作、实习和转岗使用，优先整理通用版、应届生版和设计岗版。"},
                {"index": "02", "title": "PPT模板", "body": "适合汇报、答辩和项目展示，覆盖商务风、极简风和毕业答辩常用结构。"},
                {"index": "03", "title": "Excel技巧", "body": "围绕函数、数据透视表、表格排版和常见报表处理，解决办公室高频问题。"},
            ],
            "guide_title": "怎么用最省时间",
            "guides": [
                {"title": "先看标题里的年份和版本", "body": "很多资料会因为年份、地区或考试批次不同而失效，先确认版本最稳妥。"},
                {"title": "优先用搜索框缩小范围", "body": "直接搜关键词比翻页更快，尤其适合找模板、真题和工具类资源。"},
                {"title": "下载后先核对文件名", "body": "把文件名和实际需求对应起来，避免把相近但不适用的资料误当成可用版本。"},
                {"title": "失效内容及时反馈", "body": "如果链接失效、重复或分类不准，及时反馈有助于持续清理和补充。"},
            ],
            "faq": [
                {"q": "这里的内容适合哪类用户？", "a": "适合经常找资料的人，包括学生、求职者、办公用户和需要快速定位资源的人。"},
                {"q": "为什么先做这些主题？", "a": "因为简历、PPT、Excel、真题和常用工具通常搜索量高，使用频率也更高。"},
                {"q": "会持续更新吗？", "a": "会。后续会继续把高频搜索词对应的内容补成更完整的栏目入口。"},
            ],
        },
        "study": {
            "tag": "学习入口",
            "title": "学习资料最常见的搜索方向",
            "sub": "把高考、考研、笔记和复习方法拆成明确入口，方便按场景直接查找。",
            "cards": [
                {"index": "01", "title": "高考真题", "body": "适合按年份、科目和地区查找，重点看试卷、答案和解析是否成套。"},
                {"index": "02", "title": "考研资料", "body": "适合按公共课、专业课、院校和阶段分类，降低复习资料检索成本。"},
                {"index": "03", "title": "复习笔记", "body": "把碎片知识整理成提纲、错题和冲刺版速记，更利于临考复习。"},
            ],
            "guide_title": "学习资料使用建议",
            "guides": [
                {"title": "先看科目和年份", "body": "真题、模拟卷和讲义最怕版本不对，先确认考试类型再下载。"},
                {"title": "把资料按阶段使用", "body": "基础、强化、冲刺三阶段最好分开找，学习效率会更高。"},
                {"title": "遇到空目录先别急", "body": "如果某个子栏目还没补全，可以先用一级分类的其它入口过渡。"},
                {"title": "尽量保留来源说明", "body": "便于后续查版本、找补充包和做复盘整理。"},
            ],
            "faq": [
                {"q": "高考资料为什么能继续扩充？", "a": "高考相关资料天然按年份和科目切分，后续可以很自然地补充更多批次和题型。"},
                {"q": "考研资料现在为什么比较少？", "a": "目前先把入口搭起来，后续可按院校、专业、公共课继续补齐内容。"},
                {"q": "学习栏目最适合放什么？", "a": "真题、讲义、笔记、计划表和复习工具都是非常适合的内容。"},
            ],
        },
        "work": {
            "tag": "办公高频",
            "title": "工作里最常被搜索的资料",
            "sub": "围绕简历、汇报、总结和表格处理，把办公室最常用的需求集中到一个入口。",
            "cards": [
                {"index": "01", "title": "简历模板", "body": "应届生、转岗、管理岗和设计岗都可以继续细分，适合做长期高频内容。"},
                {"index": "02", "title": "述职报告", "body": "适合按岗位、季度和行业补充，用户经常会直接搜索现成结构。"},
                {"index": "03", "title": "Excel模板", "body": "财务、行政、销售和运营常见的表格模板都有较高使用频率。"},
            ],
            "guide_title": "办公资料怎么整理更实用",
            "guides": [
                {"title": "把模板按场景拆开", "body": "简历、汇报、总结、会议纪要、计划表最好分开，不要混在一个目录。"},
                {"title": "统一文件命名", "body": "建议把岗位、年份和用途写进文件名，后期回找会省很多时间。"},
                {"title": "优先保留可编辑格式", "body": "Word、PPT、Excel 模板的可编辑版最实用，PDF 适合作为预览或归档。"},
                {"title": "记录适用场景", "body": "比如答辩、年终总结、项目复盘、述职汇报，都可以单独做入口。"},
            ],
            "faq": [
                {"q": "工作栏目最热门的内容是什么？", "a": "简历模板、PPT 模板、述职报告、会议纪要和 Excel 模板通常最常见。"},
                {"q": "为什么要强调可编辑格式？", "a": "因为工作资料很多时候要二次修改，可编辑格式能直接省下大量排版时间。"},
                {"q": "后续怎么扩展更好？", "a": "可以继续按行业、岗位和场景扩成更细的子目录。"},
            ],
        },
        "tool": {
            "tag": "工具清单",
            "title": "最实用的工具软件搜索词",
            "sub": "把常见装机工具、办公小工具和效率类软件放在同一栏，方便按用途快速定位。",
            "cards": [
                {"index": "01", "title": "PDF工具", "body": "常见需求包括合并、拆分、压缩、转 Word 和页面提取。"},
                {"index": "02", "title": "OCR识别", "body": "适合图片转文字、票据整理、截图提取和扫描件二次编辑。"},
                {"index": "03", "title": "解压与批处理", "body": "压缩包处理、批量重命名和常用脚本工具都属于高频需求。"},
            ],
            "guide_title": "工具内容的组织方式",
            "guides": [
                {"title": "按功能分类", "body": "比如办公、图片、音视频、系统维护和文件处理都可以拆分。"},
                {"title": "标注适用版本", "body": "软件类资料最容易出现版本不一致，标注版本能减少误用。"},
                {"title": "优先放常用工具", "body": "围绕 PDF、OCR、压缩解压和录屏一类高频工具最容易产生访问量。"},
                {"title": "补一段使用说明", "body": "简单说明安装、激活或使用步骤，用户体验会明显更好。"},
            ],
            "faq": [
                {"q": "工具栏目应该先放什么？", "a": "优先放 PDF、OCR、压缩、截图、录屏和常用办公辅助工具。"},
                {"q": "为什么工具类内容值得做？", "a": "因为它们搜索频率高、用途明确，而且能直接解决问题。"},
                {"q": "如果暂时没文件怎么办？", "a": "先把栏目和说明做起来，再逐步补充可下载资源。"},
            ],
        },
    }
    return packs.get(kind, packs["home"])

def _about_body(meta):
    contact = escape(meta.get("contact_email") or "zjh418094680@gmail.com")
    return (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">首页</a><span>›</span><span>关于</span></div>'
        '<h1 class="page-title"><span class="page-title-icon">📘</span>关于资料栈</h1>'
        '<div class="page-desc">整理、检索和交付实用资料的静态资料库。</div>'
        '</div></section>'
        '<section class="sec"><div class="sec-inner">'
        '<div class="category-note">资料栈强调“可找、可用、可持续维护”。页面会优先围绕高频搜索词和常见使用场景组织内容。</div>'
        '<div class="service-grid">'
        '<div class="service-card"><h3>我们做什么</h3><p>把学习、工作和工具类资料按主题拆分，减少无效翻找，提高定位效率。</p><div class="service-metrics"><span class="metric-pill">分类整理</span><span class="metric-pill">实用优先</span><span class="metric-pill">持续更新</span></div></div>'
        '<div class="service-card"><h3>内容原则</h3><p>优先做高频、实用、搜索量高的主题，例如简历、PPT、Excel、真题和常用工具。</p><div class="service-metrics"><span class="metric-pill">高频词</span><span class="metric-pill">可直接使用</span><span class="metric-pill">版本清晰</span></div></div>'
        '</div>'
        '<div style="height:12px"></div>'
        '<div class="guide-list">'
        '<div class="guide-item"><strong>适合谁</strong><span>学生、求职者、办公用户，以及需要快速查找资料的人。</span></div>'
        '<div class="guide-item"><strong>联系维护</strong><span>如果发现失效、重复或分类不准确，可通过邮箱反馈：' + contact + '。</span></div>'
        '</div>'
        '<div class="page-note">后续会继续围绕用户常搜的内容扩展栏目和子页面，让站点更像一个能直接解决问题的资料库。</div>'
        '</div></section>'
    )

def _policy_body(title, lead, points):
    items = "".join(
        '<div class="guide-item"><strong>' + escape(point["title"]) + '</strong><span>' + escape(point["body"]) + '</span></div>'
        for point in points
    )
    return (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">首页</a><span>›</span><span>' + escape(title) + '</span></div>'
        '<h1 class="page-title"><span class="page-title-icon">◎</span>' + escape(title) + '</h1>'
        '<div class="page-desc">' + escape(lead) + '</div>'
        '</div></section>'
        '<section class="sec"><div class="sec-inner">'
        '<div class="guide-list">' + items + '</div>'
        '</div></section>'
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
    temp_path = p.with_name("." + p.name + "." + str(os.getpid()) + ".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, p)
    finally:
        if temp_path.exists():
            temp_path.unlink()

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

def display_file_name(rel):
    """Return a concise human-readable label without changing the source path."""
    parts = [part.strip() for part in rel.replace("\\", "/").split("/") if part.strip()]
    filename = parts[-1] if parts else rel
    stem = re.sub(r"\.(pdf|docx?|pptx?|txt|zip|rar)$", "", filename, flags=re.IGNORECASE).strip()
    stem = stem.replace("_", " ")
    stem = re.sub(r"\s+", " ", stem)

    # Keep the source path intact, but present a cleaner title.
    stem = re.sub(r"[（(]\s*([^)）]+?)\s*[)）]", lambda m: " · " + m.group(1).strip(), stem)
    stem = re.sub(r"\s*[·•]\s*", " · ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ·")

    # If this looks like a study file path, build a concise title from the path.
    year = None
    subject = None
    for part in parts:
        if re.fullmatch(r"\d{4}", part):
            year = part
            break
    if len(parts) >= 4 and re.fullmatch(r"\d{4}", parts[2]):
        year = parts[2]
        subject = parts[3]

    if year and subject:
        body = stem
        body = re.sub(r"^" + re.escape(year) + r"\s*年?高考" + re.escape(subject), "", body)
        body = re.sub(r"^" + re.escape(year) + r"\s*高考" + re.escape(subject), "", body)
        body = re.sub(r"^" + re.escape(year) + r"\s*年?", "", body)
        body = re.sub(r"^高考" + re.escape(subject), "", body)
        body = re.sub(r"\b(试卷|试题|真题)\b", "", body)
        body = re.sub(r"\s+", " ", body).strip(" ·")
        title = year + " 高考" + subject
        if body:
            title += " · " + body
        return title

    return stem

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
        parts = [part for part in item["name"].replace("\\", "/").split("/") if part]
        if not parts:
            continue
        cs = parts[0]
        if cs not in grouped:
            continue
        grouped[cs]["count"] += 1
        if len(parts) >= 2 and parts[1] in grouped[cs]["subpages"]:
            e = dict(item)
            e["display_name"] = display_file_name(item["name"])
            grouped[cs]["subpages"][parts[1]].append(e)
        else:
            e = dict(item)
            e["display_name"] = display_file_name(item["name"])
            grouped[cs]["direct"].append(e)
    return grouped

# ── Page Builders ──────────────────────────────────────

def build_homepage(meta, grouped):
    """Generate index.html with hero, stats, category cards, and recent files."""
    pack = _content_pack("home")
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
    updated_on = datetime.now().strftime("%Y-%m-%d")

    body = "".join([
        '<section class="hero">',
        '<div class="hero-inner"><div class="hero-kicker">资料资源库</div>',
        "<h1>把分散资料，<em>整理成可查找的目录</em></h1>",
        "<p>资料栈按主题、用途和更新时间整理学习、工作、历史与工具资料，并持续检查文件入口与分类结构，让查找过程更清楚。</p>",
        '<div class="chip-nav">',
        '<span class="chip active">分类清晰</span>',
        '<span class="chip">快速检索</span>',
        '<span class="chip">直接浏览</span>',
        '<span class="chip">持续更新</span>',
        '</div>',
        '<div class="hero-actions">',
        '<a href="/cat/study.html" class="btn btn-primary">' + SEARCH_SVG + '进入资料库</a>',
        '<a href="/about.html" class="btn btn-ghost">关于本站</a>',
        '</div></div></section>',
        _ad_slot("home-top", "Place Baidu Union code here for a homepage banner or responsive block."),
        '<section class="stats">',
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">' + str(total) + '</span></div><div class="stat-label">份可用资料</div></div>',
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">' + str(len(recent)) + '</span></div><div class="stat-label">份近期更新</div></div>',
        '<div class="stat"><div class="stat-num"><span class="stat-num-grad">' + str(len(cards)) + '</span></div><div class="stat-label">个有效分类</div></div>',
        '</section>',
        '<section class="sec"><div class="sec-inner">',
        '<div class="sec-tag">' + escape(pack["tag"]) + '</div>',
        '<div class="sec-title">' + escape(pack["title"]) + '</div>',
        '<div class="sec-sub">' + escape(pack["sub"]) + '</div>',
        _render_editorial_grid(pack["cards"]),
        '</div></section>',
        '<section class="sec"><div class="sec-inner">',
        '<div class="sec-tag">近期更新</div>',
        '<div class="sec-title">最近收录</div>',
        '<div class="sec-sub">最新归档的文件，按上传时间排列。</div>',
        '<div class="file-grid">' + "".join(recent_rows) + '</div>',
        '</div></section>',
        '<section class="sec"><div class="sec-inner">',
        '<div class="sec-tag">资料导航</div>',
        '<div class="sec-title">按主题浏览</div>',
        '<div class="sec-sub">只展示已有内容的分类，减少无效入口。</div>',
        '<div class="cat-grid">' + "".join(cards) + '</div>',
        '</div></section>',
        '<section class="sec"><div class="sec-inner">',
        '<div class="sec-tag">' + escape(pack["guide_title"]) + '</div>',
        '<div class="sec-title">更快找到合适的资料</div>',
        '<div class="sec-sub">先选主题，再通过年份、地区或关键词缩小范围；文件标题会尽量保留判断内容所需的信息。</div>',
        _render_guide_list(pack["guides"]),
        '</div></section>',
        '<section class="sec"><div class="sec-inner">',
        '<div class="sec-tag">常见问题</div><div class="sec-title">关于资料栈</div>',
        _render_faq_list(pack["faq"]),
        '</div></section>',
    ])
    write_text(SITE_ROOT / "index.html", _page(meta["site_name"] + " - 分类整理的实用资料库", body, meta, show_theme_toggle=True))

def build_category_page(meta, cat, grouped):
    """Generate cat/{slug}.html with subpage cards and direct file list."""
    pack = _content_pack(cat["slug"])
    # Category chips
    chips = []
    for c in meta["categories"]:
        category_group = grouped[c["slug"]]
        category_count = len(category_group["direct"]) + sum(
            len(items) for items in category_group["subpages"].values()
        )
        if category_count == 0:
            continue
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
            if cnt == 0:
                continue
            sc.append(
                '<a href="/' + escape(cat["slug"]) + "/" + escape(sp["slug"]) + '/" class="sub-card">'
                '<div class="sub-icon" aria-hidden="true">' + _category_icon(cat["slug"]) + '</div>'
                '<div class="sub-name">' + escape(sp["name"]) + '</div>'
                '<div class="sub-desc">' + escape(sp["description"]) + " \u00b7 " + str(cnt) + " 个文件</div></a>"
            )
        if sc:
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
    file_panel = '<div class="file-panel">' + "".join(rows) + "</div>" if rows else ""

    body = "".join([
        '<section class="page-hero"><div class="wrap">',
        '<div class="breadcrumbs"><a href="/">首页</a><span>\u203a</span>',
        "<span>" + escape(cat["name"]) + "</span></div>",
        '<h1 class="page-title"><span class="page-title-icon">' + _category_icon(cat["slug"]) + '</span>' + escape(cat["name"]) + '</h1>',
        '<div class="page-desc">' + escape(cat["description"]) + '</div>',
        '<div class="chip-nav">' + "".join(chips) + '</div></div></section>',
        '<section class="sec"><div class="sec-inner">',
        _ad_slot("category-top", "Place Baidu Union code here for category pages."),
        '<div class="category-note">本栏目按主题和用途整理资料。下载或使用前，请结合文件标题、年份和版本信息判断是否符合需要；如发现失效、重复或分类不准确，可通过页脚邮箱反馈。</div>',
        '<div class="sec-tag">' + escape(pack["tag"]) + '</div>',
        '<div class="sec-title">' + escape(pack["title"]) + '</div>',
        '<div class="sec-sub">' + escape(pack["sub"]) + '</div>',
        _render_editorial_grid(pack["cards"]),
        '<div style="height:12px"></div>',
        '<div class="sec-tag">使用建议</div>',
        '<div class="sec-title">把这一类资料用起来</div>',
        '<div class="sec-sub">这部分内容更像快速导览，方便用户先判断该栏目是否适合自己的需求。</div>',
        _render_guide_list(pack["guides"]),
        '<div style="height:12px"></div>',
        '<div class="sec-tag">常见问题</div>',
        '<div class="sec-title">关于 ' + escape(cat["name"]) + '</div>',
        _render_faq_list(pack["faq"]),
        sub_cards,
        file_panel,
        '</div></section>',
    ])
    write_text(CATEGORY_DIR / (cat["slug"] + ".html"), _page(cat["name"] + " - " + SITE_NAME, body, meta))

def build_subpage(meta, cat, sp, sp_items):
    """Generate {category}/{subpage}/index.html with search + pagination."""
    pack = _content_pack(cat["slug"])
    if cat["slug"] == "study" and sp["slug"] == "gaokao":
        sub_tag = "真题归档"
        sub_title = "高考资料的查找重点"
        sub_sub = "真题、模拟卷和答案解析最适合按年份、科目和地区筛选。"
        sub_cards = [
            {"index": "01", "title": "年份优先", "body": "先找对应年份，再确认科目和地区，避免下载到相近但不匹配的试卷。"},
            {"index": "02", "title": "试卷配套", "body": "尽量同时保留试题、答案和解析，方便后续对照复盘。"},
            {"index": "03", "title": "冲刺复习", "body": "适合在模考和冲刺阶段集中使用，快速定位高频考点。"},
        ]
        sub_guides = [
            {"title": "按学科进入", "body": "从语文、数学、英语和选科开始找最省事。"},
            {"title": "先看题型结构", "body": "了解试卷结构后，再决定是否继续下载同类年份内容。"},
            {"title": "优先成套整理", "body": "真题、答案和解析成套存放更容易复习。"},
            {"title": "遇到缺卷先反馈", "body": "空缺年份或版本不完整时，及时标记方便后续补齐。"},
        ]
        sub_faq = [
            {"q": "高考资料适合什么人？", "a": "适合需要真题、模拟卷和答案解析的学生或老师。"},
            {"q": "为什么要按年份找？", "a": "因为高考题型和政策会变化，年份是最可靠的入口。"},
            {"q": "资料缺少解析怎么办？", "a": "可以先看题目和答案，后续再补完整解析包。"},
        ]
    elif cat["slug"] == "study" and sp["slug"] == "kaoyan":
        sub_tag = "考研准备"
        sub_title = "考研资料最实用的拆分方式"
        sub_sub = "公共课、专业课、院校信息和阶段计划分开整理，复习效率会更高。"
        sub_cards = [
            {"index": "01", "title": "公共课", "body": "政治、英语和数学可以按题型、阶段和老师版本分别归档。"},
            {"index": "02", "title": "专业课", "body": "按院校和专业编号整理，避免不同学校的参考书混在一起。"},
            {"index": "03", "title": "复习计划", "body": "把基础、强化和冲刺拆成不同资料，方便逐步推进。"},
        ]
        sub_guides = [
            {"title": "先按院校分类", "body": "考研资料最重要的是院校和专业对应关系。"},
            {"title": "把讲义和笔记分开", "body": "讲义负责系统学习，笔记负责查漏补缺。"},
            {"title": "给每份资料写用途", "body": "标明是基础、强化还是冲刺阶段更利于回看。"},
            {"title": "先做可用入口", "body": "即使暂时资料不多，也先把结构和说明搭起来。"},
        ]
        sub_faq = [
            {"q": "考研资料怎么最有效？", "a": "优先按学校、专业和阶段整理，而不是简单堆文件。"},
            {"q": "为什么这里先做入口？", "a": "因为考研资料适合先定结构，再持续补内容。"},
            {"q": "后续可以扩展什么？", "a": "可以继续加院校真题、专业课笔记和复习规划表。"},
        ]
    else:
        sub_tag = pack["tag"]
        sub_title = pack["title"]
        sub_sub = pack["sub"]
        sub_cards = pack["cards"]
        sub_guides = pack["guides"]
        sub_faq = pack["faq"]

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

    body = "".join([
        '<section class="page-hero"><div class="wrap">',
        '<div class="breadcrumbs"><a href="/">首页</a><span>\u203a</span>',
        '<a href="/cat/' + escape(cat["slug"]) + '.html">' + escape(cat["name"]) + '</a>',
        "<span>\u203a</span><span>" + escape(sp["name"]) + "</span></div>",
        '<h1 class="page-title"><span class="page-title-icon">' + _category_icon(cat["slug"]) + '</span>' + escape(sp["name"]) + '</h1>',
        '<div class="page-desc">' + escape(sp["description"]) + '</div>',
        '<div class="chip-nav"><a class="chip" href="/cat/' + escape(cat["slug"]) + '.html">\u2190 返回</a></div></div></section>',
        '<section class="sec"><div class="sec-inner">',
        '<div class="sec-tag">' + escape(sub_tag) + '</div>',
        '<div class="sec-title">' + escape(sub_title) + '</div>',
        '<div class="sec-sub">' + escape(sub_sub) + '</div>',
        _render_editorial_grid(sub_cards),
        '<div style="height:12px"></div>',
        '<div class="sec-tag">使用建议</div>',
        '<div class="sec-title">进入之前先看这几点</div>',
        '<div class="sec-sub">子页面更适合做成“直接可用”的入口，先看这里能不能覆盖你的需求，再去搜索具体文件。</div>',
        _render_guide_list(sub_guides),
        '<div style="height:12px"></div>',
        '<div class="sec-tag">常见问题</div>',
        '<div class="sec-title">关于 ' + escape(sp["name"]) + '</div>',
        _render_faq_list(sub_faq),
        '<div class="toolbar"><input type="text" class="search-input" id="s" placeholder="搜索文件..."></div>',
        _ad_slot("subpage-top", "Optional ad slot above the searchable file list."),
        '<div class="file-panel" id="p"></div>',
        '<div class="pg-bar">',
        '<select class="pg-size-select" id="z">',
        '<option value="10">10条/页</option><option value="30" selected>30条/页</option>',
        '<option value="50">50条/页</option></select>',
        '<div id="n"></div><span class="pg-info" id="i"></span>',
        '</div></div></section>',
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
    ])

    sp_dir = SITE_ROOT / cat["slug"] / sp["slug"]
    sp_dir.mkdir(parents=True, exist_ok=True)
    write_text(sp_dir / "index.html", _page(sp["name"] + " - " + cat["name"] + " - " + SITE_NAME, body, meta))

# ── Build Orchestrator ─────────────────────────────────

def build_membership_page(meta):
    """Generate member.html with a restrained membership pitch."""
    contact = escape(meta.get("contact_email") or "zjh418094680@gmail.com")
    body = (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">首页</a><span>\u203a</span><span>会员</span></div>'
        '<h1 class="page-title"><span class="page-title-icon">☆</span>会员</h1>'
        '<div class="page-desc">把常用资料、批量下载和更新提醒放到一处，减少反复找文件的时间。</div>'
        '<div class="chip-nav"><a class="chip active" href="/member.html">会员方案</a><a class="chip" href="/custom.html">企业定制</a></div>'
        '</div></section>'
        '<section class="sec"><div class="sec-inner">'
        '<div class="sec-tag">适合个人用户</div>'
        '<div class="sec-title">免费可以看，会员可以更快</div>'
        '<div class="sec-sub">基础浏览保持开放，会员服务只解决高频、重复、耗时的动作。</div>'
        '<div class="service-grid">'
        '<div class="service-card"><h3>搜索增强</h3><p>按标题、分类、时间和关键词更快定位资料，少翻页，少绕路。</p><div class="service-metrics"><span class="metric-pill">全文检索</span><span class="metric-pill">收藏夹</span><span class="metric-pill">最近浏览</span></div></div>'
        '<div class="service-card"><h3>下载加速</h3><p>高频下载场景更适合会员，保留更顺手的获取路径和下载记录。</p><div class="service-metrics"><span class="metric-pill">批量下载</span><span class="metric-pill">下载历史</span><span class="metric-pill">专属入口</span></div></div>'
        '</div>'
        '<div style="height:12px"></div>'
        '<div class="service-grid">'
        '<div class="offer-card"><div class="offer-top"><div class="offer-kicker">月卡</div><div class="offer-kicker">试用型</div></div><div class="offer-title">先试用，再决定</div><div class="offer-desc">适合短期高频找资料的用户，先把效率提升起来。</div><ul class="offer-list"><li>连续下载更顺手</li><li>优先体验新功能</li><li>适合临时冲刺场景</li></ul><div class="offer-actions"><a class="btn btn-primary" href="mailto:' + contact + '?subject=%E4%BC%9A%E5%91%98%E5%BC%80%E9%80%9A">联系开通</a></div></div>'
        '<div class="offer-card"><div class="offer-top"><div class="offer-kicker">年卡</div><div class="offer-kicker">主推</div></div><div class="offer-title">长期使用更划算</div><div class="offer-desc">适合经常来找资料的用户，省掉反复切换和重复查找。</div><ul class="offer-list"><li>更适合长期积累</li><li>操作路径更短</li><li>持续更新更省心</li></ul><div class="offer-actions"><a class="btn btn-primary" href="mailto:' + contact + '?subject=%E5%B9%B4%E5%8D%A1%E4%BC%9A%E5%91%98">联系开通</a></div></div>'
        '</div>'
        '<div class="page-note">说明：公开内容继续免费浏览，会员主要覆盖效率型能力，不影响普通访客的基本访问。</div>'
        '<div class="cta-band"><div><strong>如果你只是偶尔来一次，就继续免费用。</strong><span>如果你经常查找、下载、整理资料，会员会更省时间。</span></div><a class="btn btn-primary" href="mailto:' + contact + '?subject=%E4%BC%9A%E5%91%98%E5%92%A8%E8%AF%A2">邮件咨询</a></div>'
        '</div></section>'
    )
    write_text(SITE_ROOT / "member.html", _page("会员 - " + SITE_NAME, body, meta))

def build_custom_page(meta):
    """Generate custom.html for enterprise/custom service inquiries."""
    contact = escape(meta.get("contact_email") or "zjh418094680@gmail.com")
    body = (
        '<section class="page-hero"><div class="wrap">'
        '<div class="breadcrumbs"><a href="/">首页</a><span>\u203a</span><span>定制</span></div>'
        '<h1 class="page-title"><span class="page-title-icon">◎</span>企业定制</h1>'
        '<div class="page-desc">如果你需要的是团队内部的资料整理、权限控制和私有化部署，这一层更合适。</div>'
        '<div class="chip-nav"><a class="chip" href="/member.html">会员方案</a><a class="chip active" href="/custom.html">企业定制</a></div>'
        '</div></section>'
        '<section class="sec"><div class="sec-inner">'
        '<div class="sec-tag">适合团队 / 机构</div>'
        '<div class="sec-title">不是卖页面，而是交付可用的资料系统</div>'
        '<div class="sec-sub">我们把需求拆成结构、权限、内容、部署和运维，适合长期跑的项目。</div>'
        '<div class="service-grid">'
        '<div class="service-card"><h3>私有部署</h3><p>可按你的域名、服务器和访问方式部署，保留团队自己的内容边界。</p><div class="service-metrics"><span class="metric-pill">独立域名</span><span class="metric-pill">服务器部署</span><span class="metric-pill">HTTPS</span></div></div>'
        '<div class="service-card"><h3>权限分层</h3><p>公开内容、会员内容、内部内容可以分层放置，访问规则清楚。</p><div class="service-metrics"><span class="metric-pill">公开区</span><span class="metric-pill">会员区</span><span class="metric-pill">内部区</span></div></div>'
        '<div class="service-card"><h3>资料整理</h3><p>把原始文件、命名规则、分类结构整理成可长期维护的资料库。</p><div class="service-metrics"><span class="metric-pill">分类规划</span><span class="metric-pill">批量入库</span><span class="metric-pill">标签体系</span></div></div>'
        '<div class="service-card"><h3>后续维护</h3><p>包含更新、优化和常见故障处理，避免站点上线后很快失控。</p><div class="service-metrics"><span class="metric-pill">定期更新</span><span class="metric-pill">故障响应</span><span class="metric-pill">优化建议</span></div></div>'
        '</div>'
        '<div class="cta-band"><div><strong>如果你要的是“能赚钱的资料站”，先把结构做对。</strong><span>我们可以按你的内容类型、目标用户和预算，拆成可执行的版本。</span></div><a class="btn btn-primary" href="mailto:' + contact + '?subject=%E4%BC%81%E4%B8%9A%E5%AE%9A%E5%88%B6%E5%92%A8%E8%AF%A2">发邮件定制</a></div>'
        '<div class="page-note">定制合作建议先从分类和交付方式入手，再决定会员、付费下载或项目制交付。</div>'
        '</div></section>'
    )
    write_text(SITE_ROOT / "custom.html", _page("定制 - " + SITE_NAME, body, meta))

def build_about_page(meta):
    """Generate about.html."""
    write_text(SITE_ROOT / "about.html", _page("关于 - " + SITE_NAME, _about_body(meta), meta))

def build_privacy_page(meta):
    """Generate privacy.html."""
    body = _policy_body(
        "隐私政策",
        "说明站点在收集、使用和保存访问相关信息时的基本原则。",
        [
            {"title": "信息收集范围", "body": "站点仅保留实现服务所需的基础访问数据，不主动收集与内容无关的个人敏感信息。"},
            {"title": "数据使用方式", "body": "数据主要用于页面展示、基本统计、问题排查和站点维护。"},
            {"title": "第三方链接", "body": "若页面链接到外部文件或站外资源，请以对方站点的规则为准。"},
            {"title": "联系反馈", "body": "若你希望删除、修正或更新相关内容，可以通过站内邮箱联系我们。"},
        ],
    )
    write_text(SITE_ROOT / "privacy.html", _page("隐私政策 - " + SITE_NAME, body, meta))

def build_terms_page(meta):
    """Generate terms.html."""
    body = _policy_body(
        "服务条款",
        "说明访问、使用与反馈资料内容时需要遵守的基础约定。",
        [
            {"title": "合理使用", "body": "请将站点内容用于学习、办公、研究和资料整理等合法场景。"},
            {"title": "内容准确性", "body": "本站尽量保持标题与分类准确，但实际内容仍以文件本身为准。"},
            {"title": "版权尊重", "body": "如资料存在版权争议或来源问题，将根据反馈进行修正或下架。"},
            {"title": "规则更新", "body": "当站点内容或维护方式变化时，本页也会同步更新说明。"},
        ],
    )
    write_text(SITE_ROOT / "terms.html", _page("服务条款 - " + SITE_NAME, body, meta))

def build_all(meta=None):
    """Run full build: scan files, generate all pages. Returns stats dict."""
    meta = meta or load_meta()
    items = write_files_json(meta)
    grouped = group_files(meta, items)
    for c in meta["categories"]:
        c["_count"] = grouped[c["slug"]]["count"]
    CATEGORY_DIR.mkdir(parents=True, exist_ok=True)

    build_homepage(meta, grouped)
    build_about_page(meta)
    build_privacy_page(meta)
    build_terms_page(meta)
    build_membership_page(meta)
    build_custom_page(meta)
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
        + [SITE_ROOT / "member.html", SITE_ROOT / "custom.html"]
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
