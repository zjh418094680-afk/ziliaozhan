#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
from html import escape
from urllib.parse import parse_qs, quote

FILES_JSON = "/var/www/materials/files.json"


def load_files():
    if not os.path.exists(FILES_JSON):
        return []
    with open(FILES_JSON, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_name(name):
    return str(name or "").replace("\\", "/").replace("//", "/").lstrip("/")


def search_files(query):
    keyword = (query or "").strip().lower()
    if not keyword:
        return []

    results = []
    for item in load_files():
        name = normalize_name(item.get("name"))
        lowered = name.lower()
        base_name = lowered.rsplit("/", 1)[-1]
        if keyword in lowered or keyword in base_name:
            safe_path = quote(name, safe="/-_.() ")
            results.append(
                {
                    "name": name,
                    "url": "/" + safe_path.replace(" ", "%20"),
                    "size": item.get("size", "--"),
                    "modified": item.get("modified", "--"),
                }
            )
    return results[:200]


def render_page(query, results):
    title = f"搜索结果 - {query}" if query else "文件搜索"
    if results:
        cards = []
        for item in results:
            cards.append(
                f"""
                <a class="result-item" href="{escape(item['url'])}" target="_blank" rel="noopener noreferrer">
                    <div class="result-title">{escape(item['name'].rsplit('/', 1)[-1])}</div>
                    <div class="result-meta">
                        <span>{escape(item['name'])}</span>
                        <span>{escape(str(item['modified']))}</span>
                    </div>
                </a>
                """
            )
        result_html = "".join(cards)
    else:
        result_html = '<div class="empty">没有找到匹配的文件名</div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;background:#0F172A;color:#F1F5F9}}
.wrap{{width:min(1100px,calc(100vw - 32px));margin:0 auto;padding:32px 0 48px}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}}
.title{{font-size:clamp(28px,4vw,44px);margin:0}}
.back{{color:#60A5FA;text-decoration:none;font-weight:700}}
.search{{margin:24px 0;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px}}
.search input{{width:100%;min-width:0;padding:14px 16px;border-radius:18px;border:1px solid #334155;background:#1E293B;color:#F1F5F9}}
.search button{{padding:14px 18px;border:0;border-radius:18px;background:#3B82F6;color:#fff;font-weight:700;cursor:pointer}}
.summary{{color:#94A3B8;font-size:14px;margin:10px 0 18px}}
.results{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
.result-item{{display:block;background:#1E293B;border:1px solid #334155;border-radius:16px;padding:16px;color:inherit;text-decoration:none;transition:border-color .2s,transform .2s}}
.result-item:hover{{border-color:#60A5FA;transform:translateY(-2px)}}
.result-title{{font-weight:800;margin-bottom:8px;word-break:break-word}}
.result-meta{{display:flex;justify-content:space-between;gap:10px;color:#94A3B8;font-size:12px;flex-wrap:wrap}}
.empty{{padding:28px 16px;border:1px dashed #334155;border-radius:16px;color:#94A3B8;text-align:center}}
@media(max-width:640px){{
  .wrap{{width:min(100%,calc(100vw - 20px));padding:24px 0 36px}}
  .search{{grid-template-columns:1fr}}
  .search button{{width:100%}}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1 class="title">{escape(title)}</h1>
    <a class="back" href="/">返回首页</a>
  </div>
  <form class="search" action="/api/search" method="get">
    <input name="q" value="{escape(query)}" placeholder="继续搜索文件名">
    <button type="submit">搜索</button>
  </form>
  <div class="summary">找到 {len(results)} 个结果</div>
  <div class="results">{result_html}</div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    print("Content-Type: text/html; charset=utf-8")
    print()
    query = parse_qs(os.environ.get("QUERY_STRING", "")).get("q", [""])[0]
    print(render_page(query, search_files(query)))
