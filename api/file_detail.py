#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件详情 API：返回单个文件的详细信息
"""
import os
import json
from datetime import datetime

MATERIALS_DIR = '/var/www/materials'

def safe_path(base_dir, user_path):
    """
    Resolve a user-provided path safely under base_dir.
    Reject absolute paths and path traversal.
    """
    if not user_path:
        return None

    # Disallow absolute paths and Windows separators.
    if os.path.isabs(user_path) or '\\' in user_path:
        return None

    # Normalize and ensure the resolved path stays within base_dir.
    base_real = os.path.realpath(base_dir)
    candidate = os.path.realpath(os.path.join(base_real, user_path))
    if candidate == base_real or not candidate.startswith(base_real + os.sep):
        return None
    return candidate

def get_file_detail(name):
    path = safe_path(MATERIALS_DIR, name)
    if not path:
        return None
    if not os.path.exists(path):
        return None
    
    stat = os.stat(path)
    is_dir = os.path.isdir(path)
    
    detail = {
        'name': name,
        'is_dir': is_dir,
        'size': stat.st_size if not is_dir else 0,
        'size_display': format_size(stat.st_size) if not is_dir else '--',
        'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'accessed': datetime.fromtimestamp(stat.st_atime).strftime('%Y-%m-%d %H:%M:%S'),
        'url': '/' + name.lstrip('/'),
        'permissions': oct(stat.st_mode)[-3:],
    }
    
    # 如果是压缩包，尝试获取内容列表
    if not is_dir:
        ext = name.split('.')[-1].lower()
        if ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
            detail['archive_type'] = ext
            detail['archive_contents'] = get_archive_contents(path, ext)
    
    return detail

def format_size(bytes):
    if bytes == 0: return '0 B'
    units = ['B', 'KB', 'MB', 'GB']
    i = 0
    while bytes >= 1024 and i < 3:
        bytes /= 1024
        i += 1
    return f'{bytes:.1f} {units[i]}'

def get_archive_contents(path, ext):
    """获取压缩包内容列表"""
    import subprocess
    try:
        if ext == 'zip':
            result = subprocess.run(['unzip', '-l', path], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')[3:-2]  # 跳过头部
            files = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    size = parts[0]
                    name = ' '.join(parts[3:])
                    if name and not name.startswith('__MACOSX'):
                        files.append({'name': name, 'size': size})
            return files[:20]  # 只返回前20个
        elif ext in ['tar', 'gz', 'bz2']:
            result = subprocess.run(['tar', '-tf', path], capture_output=True, text=True, timeout=10)
            files = [{'name': f, 'size': '--'} for f in result.stdout.strip().split('\n')[:20]]
            return files
        elif ext == '7z':
            result = subprocess.run(['7z', 'l', path], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')[7:-2]
            files = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 3:
                    size = parts[2]
                    name = ' '.join(parts[3:])
                    if name:
                        files.append({'name': name, 'size': size})
            return files[:20]
    except Exception as e:
        return [{'error': str(e)}]
    return []

if __name__ == '__main__':
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else ''
    
    # CGI 模式
    print('Content-Type: application/json')
    print()
    
    if not name:
        print(json.dumps({'error': 'No file specified'}))
    else:
        detail = get_file_detail(name)
        if detail:
            print(json.dumps(detail, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({'error': 'File not found'}))
