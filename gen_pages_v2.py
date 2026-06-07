# -*- coding: utf-8 -*-
"""
资料栈 - 分类分页生成器 v2.0
生成 study/省份/科目/_N.html 分页页面
完全兼容微信浏览器：零CSS var()、零ES6、零fetch、事件委托
"""
import os, json, math
from datetime import datetime
from urllib.parse import quote

FILES_PER_PAGE = 80
SITE_ROOT = '/var/www/materials'

PROVINCES = {
    'beijing': '北京', 'shanghai': '上海', 'tianjin': '天津', 'chongqing': '重庆',
    'guangdong': '广东', 'jiangsu': '江苏', 'zhejiang': '浙江', 'fujian': '福建',
    'hubei': '湖北', 'hunan': '湖南', 'hebei': '河北', 'henan': '河南',
    'shandong': '山东', 'sichuan': '四川', 'anhui': '安徽', 'jiangxi': '江西',
    'guangxi': '广西', 'yunnan': '云南', 'guizhou': '贵州', 'hainan': '海南',
    'liaoning': '辽宁', 'jilin': '吉林', 'heilongjiang': '黑龙江',
    'shanxi': '山西', 'shaanxi': '陕西', 'gansu': '甘肃', 'qinghai': '青海',
    'ningxia': '宁夏', 'xinjiang': '新疆', 'neimenggu': '内蒙古', 'xizang': '西藏',
}

SUBJECTS = {
    'yuwen': '语文', 'shuxue': '数学', 'yingyu': '英语',
    'wuli': '物理', 'huaxue': '化学', 'shengwu': '生物',
    'zhengzhi': '政治', 'lishi': '历史', 'dili': '地理', 'zonghe': '综合',
}

def format_size(bytes_val):
    if not bytes_val or bytes_val == 0:
        return '--'
    units = ['B', 'KB', 'MB', 'GB']
    i, s = 0, float(bytes_val)
    while s >= 1024 and i < 3:
        s /= 1024; i += 1
    return f'{s:.1f} {units[i]}' if i > 0 else f'{int(s)} {units[i]}'

def escape_html(text):
    return (
        str(text)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;')
    )

def escape_attr(text):
    return escape_html(text)

print("gen_pages_v2.py loaded - ready")

def build_pagination(current, total, base_url):
    """生成分页HTML"""
    if total <= 1:
        return ''
    parts = []
    if current > 1:
        prev = base_url + ('index.html' if current == 2 else ('_' + str(current - 1) + '.html'))
        parts.append('<a href="' + prev + '" class="page-btn">&#8249;</a>')
    else:
        parts.append('<span class="page-btn disabled">&#8249;</span>')
    
    pages = []
    if total <= 7:
        pages = list(range(1, total + 1))
    else:
        pages.append(1)
        if current > 3:
            pages.append('...')
        for p in range(max(2, current - 1), min(total, current + 2)):
            pages.append(p)
        if current < total - 2:
            pages.append('...')
        pages.append(total)
    
    for p in pages:
        if p == '...':
            parts.append('<span class="page-ellipsis">...</span>')
        elif p == current:
            parts.append('<span class="page-btn active">' + str(p) + '</span>')
        else:
            url = base_url + ('index.html' if p == 1 else ('_' + str(p) + '.html'))
            parts.append('<a href="' + url + '" class="page-btn">' + str(p) + '</a>')
    
    if current < total:
        parts.append('<a href="' + base_url + '_' + str(current + 1) + '.html" class="page-btn">&#8250;</a>')
    else:
        parts.append('<span class="page-btn disabled">&#8250;</span>')
    
    return '\n'.join('        ' + p for p in parts)


def file_item_html(name, url, size, date):
    return (
        '        <li class="file-item">\n'
        '            <span class="file-name"><a href="' + escape_attr(url) + '" target="_blank">' + escape_html(name) + '</a></span>\n'
        '            <span class="file-size">' + format_size(size) + '</span>\n'
        '            <span class="file-date">' + str(date)[:10] + '</span>\n'
        '        </li>'
    )


# ===== 页面生成 =====
import os as _os

_TEMPLATE_DIR = _os.path.dirname(_os.path.abspath(__file__))

def _load_template(name):
    with open(_os.path.join(_TEMPLATE_DIR, name), 'r', encoding='utf-8') as f:
        return f.read()

def generate_subject_page(province_key, province_name, subject_key, subject_name, 
                          files, page_num, total_pages):
    """生成科目分页"""
    tpl = _load_template('tpl_page.html')
    base = f'/study/{province_key}/{subject_key}/'
    
    # 文件列表
    file_items = []
    for f in files:
        file_items.append(file_item_html(
            f.get('name', ''), f.get('url', '#'), f.get('size', 0), f.get('modified', '--')
        ))
    
    # 分页
    pagination = build_pagination(page_num, total_pages, base)
    
    # 上一页链接
    if page_num == 1:
        back_url = f'/study/{province_key}/'
        back_label = province_name
    else:
        back_url = base + 'index.html'
        back_label = subject_name
    
    html = tpl.replace('{{TITLE}}', f'{province_name} · {subject_name} 第{page_num}页 - 资料栈')
    html = html.replace('{{BACK_URL}}', back_url)
    html = html.replace('{{BACK_LABEL}}', back_label)
    html = html.replace('{{PROVINCE_URL}}', f'/study/{province_key}/')
    html = html.replace('{{PROVINCE}}', province_name)
    html = html.replace('{{SUBJECT}}', subject_name)
    html = html.replace('{{TOTAL_FILES}}', str(len(files)))
    html = html.replace('{{PAGE}}', str(page_num))
    html = html.replace('{{TOTAL_PAGES}}', str(total_pages))
    html = html.replace('{{FILE_LIST}}', '\n'.join(file_items))
    html = html.replace('{{PAGINATION}}', pagination)
    
    return html


def generate_province_page(province_key, province_name, subjects):
    """生成省份选择页"""
    tpl = _load_template('tpl_province.html')
    
    cards = []
    for sk, sn in subjects.items():
        cards.append(
            '<a href="' + sk + '/" class="subject-card">'
            '<div class="subject-icon">📖</div>'
            '<div class="subject-name">' + sn + '</div>'
            '<div class="subject-arrow">→</div>'
            '</a>'
        )
    
    html = tpl.replace('{{TITLE}}', province_name + ' 高考真题 - 资料栈')
    html = html.replace('{{PROVINCE}}', province_name)
    html = html.replace('{{SUBJECT_CARDS}}', '\n'.join(cards))
    
    return html


def scan_files(base_dir):
    """扫描目录，返回文件列表"""
    result = []
    if not _os.path.exists(base_dir):
        return result
    for name in sorted(_os.listdir(base_dir)):
        path = _os.path.join(base_dir, name)
        if _os.path.isfile(path):
            stat = _os.stat(path)
            rel = _os.path.relpath(path, SITE_ROOT).replace('\\', '/')
            url = quote('/' + rel, safe='/-_.~')
            result.append({
                'name': name,
                'url': url,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
            })
    return result


def generate_study_structure(source_dir, output_dir):
    """
    从源目录生成完整 study 分页结构
    source_dir: 源数据目录 (如 D:/leidian/2025各省市高考真题/)
    output_dir: 输出目录 (如 /var/www/materials/study/)
    """
    _os.makedirs(output_dir, exist_ok=True)
    total_pages_generated = 0
    
    # 扫描源目录下的省份
    for entry in sorted(_os.listdir(source_dir)):
        entry_path = _os.path.join(source_dir, entry)
        if not _os.path.isdir(entry_path):
            continue
        
        # 匹配省份名
        province_key = None
        province_name = None
        for pk, pn in PROVINCES.items():
            if pn in entry or pk in entry.lower():
                province_key = pk
                province_name = pn
                break
        if not province_key:
            continue
        
        prov_dir = _os.path.join(output_dir, province_key)
        _os.makedirs(prov_dir, exist_ok=True)
        
        # 扫描科目
        subjects_found = {}
        for sub_entry in sorted(_os.listdir(entry_path)):
            sub_path = _os.path.join(entry_path, sub_entry)
            if not _os.path.isdir(sub_path):
                continue
            
            subject_key = None
            subject_name = None
            for sk, sn in SUBJECTS.items():
                if sn in sub_entry or sk in sub_entry.lower():
                    subject_key = sk
                    subject_name = sn
                    break
            if not subject_key:
                continue
            
            subjects_found[subject_key] = subject_name
            files = scan_files(sub_path)
            
            if not files:
                continue
            
            total_pages = (len(files) + FILES_PER_PAGE - 1) // FILES_PER_PAGE
            subj_dir = _os.path.join(prov_dir, subject_key)
            _os.makedirs(subj_dir, exist_ok=True)
            
            for page in range(1, total_pages + 1):
                start = (page - 1) * FILES_PER_PAGE
                end = start + FILES_PER_PAGE
                page_files = files[start:end]
                
                html = generate_subject_page(
                    province_key, province_name,
                    subject_key, subject_name,
                    page_files, page, total_pages
                )
                
                if page == 1:
                    out_path = _os.path.join(subj_dir, 'index.html')
                else:
                    out_path = _os.path.join(subj_dir, f'_{page}.html')
                
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                total_pages_generated += 1
            
            print(f'  {province_name}/{subject_name}: {total_pages} pages ({len(files)} files)')
        
        # 生成省份页
        if subjects_found:
            prov_html = generate_province_page(province_key, province_name, subjects_found)
            with open(_os.path.join(prov_dir, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(prov_html)
    
    print(f'\nTotal pages generated: {total_pages_generated}')
    return total_pages_generated


# ===== CLI =====
if __name__ == '__main__':
    import sys
    print("资料栈分页生成器 v2.0")
    print(f"每页: {FILES_PER_PAGE} 文件 | 兼容: 微信浏览器")
    if len(sys.argv) >= 3:
        generate_study_structure(sys.argv[1], sys.argv[2])
    else:
        print("用法: python gen_pages_v2.py <源目录> <输出目录>")
        print("示例: python gen_pages_v2.py 'D:/leidian/2025各省市高考真题' '/var/www/materials/study/'")
