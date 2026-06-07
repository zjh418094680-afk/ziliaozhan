#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
访问统计 API：记录和查询文件访问/下载日志
"""
import os
import json
from datetime import datetime, timedelta
import gzip

LOG_FILE = '/var/log/nginx/access.log'
STATS_FILE = '/var/www/materials/stats.json'
HOURS_TO_KEEP = 168  # 保留7天

def parse_log_line(line, client_ip):
    """解析 Nginx 日志行，提取文件访问信息"""
    try:
        parts = line.split('"')
        if len(parts) < 3:
            return None
        
        request = parts[1].split()
        if len(request) < 2:
            return None
        
        method, path = request[0], request[1]
        
        # 只统计对 materials 目录下文件的请求
        if not path.startswith('/materials/') and not path.startswith('/files.json'):
            if path != '/':
                return None
        
        # 提取文件名
        filename = path.split('/')[-1]
        if not filename:
            return None
        
        # 过滤掉非文件请求
        if filename in ['', 'index.html', 'files.json', 'stats.json']:
            return None
        
        # 判断是下载还是查看
        is_download = 'download' in path.lower() or method == 'GET'
        
        return {
            'filename': filename,
            'method': method,
            'timestamp': datetime.now().isoformat(),
        }
    except:
        return None

def load_stats():
    """加载现有统计数据"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'daily': {}, 'files': {}, 'total_views': 0, 'total_downloads': 0}

def save_stats(stats):
    """保存统计数据"""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def process_logs():
    """处理 Nginx 日志，更新统计数据"""
    if not os.path.exists(LOG_FILE):
        return None
    
    stats = load_stats()
    
    # 日志可能很大，只读最后 1MB
    try:
        with open(LOG_FILE, 'rb') as f:
            f.seek(max(0, os.path.getsize(LOG_FILE) - 1024*1024))
            lines = f.read().decode('utf-8', errors='ignore').split('\n')
    except:
        return None
    
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 初始化今天的统计数据
    if today not in stats['daily']:
        stats['daily'][today] = {'views': 0, 'downloads': 0}
    
    # 更新昨日数据
    if yesterday not in stats['daily']:
        stats['daily'][yesterday] = {'views': 0, 'downloads': 0}
    
    for line in lines:
        info = parse_log_line(line, '')
        if not info:
            continue
        
        fname = info['filename']
        
        # 更新文件统计
        if fname not in stats['files']:
            stats['files'][fname] = {'views': 0, 'downloads': 0}
        
        # 更新今日统计
        stats['daily'][today]['views'] += 1
        stats['files'][fname]['views'] += 1
        stats['total_views'] += 1
        
        # 如果是下载请求
        if info['method'] == 'GET' and '.' in fname:
            stats['daily'][today]['downloads'] += 1
            stats['files'][fname]['downloads'] = stats['files'][fname].get('downloads', 0) + 1
            stats['total_downloads'] += 1
    
    # 清理旧数据（保留7天）
    cutoff = (datetime.now() - timedelta(hours=HOURS_TO_KEEP)).strftime('%Y-%m-%d')
    stats['daily'] = {k: v for k, v in stats['daily'].items() if k >= cutoff}
    
    save_stats(stats)
    return stats

def get_top_files(limit=10):
    """获取热门文件排行"""
    stats = load_stats()
    files = sorted(stats.get('files', {}).items(), key=lambda x: x[1].get('views', 0), reverse=True)
    return [
        {
            'name': name,
            'views': data.get('views', 0),
            'downloads': data.get('downloads', 0),
        }
        for name, data in files[:limit]
    ]

def get_trend(days=7):
    """获取访问趋势"""
    stats = load_stats()
    trend = []
    for i in range(days):
        d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        data = stats['daily'].get(d, {'views': 0, 'downloads': 0})
        trend.insert(0, {'date': d, 'views': data.get('views', 0), 'downloads': data.get('downloads', 0)})
    return trend

if __name__ == '__main__':
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    
    print('Content-Type: application/json')
    print()
    
    if action == 'process':
        result = process_logs()
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else json.dumps({'ok': True}))
    elif action == 'top':
        print(json.dumps(get_top_files(), ensure_ascii=False, indent=2))
    elif action == 'trend':
        print(json.dumps(get_trend(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(load_stats(), ensure_ascii=False, indent=2))