#!/usr/bin/env python3
import os, json, re, gzip, sys, time
from datetime import datetime
from collections import defaultdict
from pathlib import Path

LOG_DIR = '/var/log/nginx'
CACHE_FILE = '/var/www/materials/stats_cache.json'
GEO_CACHE = '/var/www/materials/api/geo_cache.json'
CACHE_TTL = 300

def load_json(path, default={}):
    if os.path.exists(path):
        try:
            with open(path) as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f)

def ip_to_geo(ip):
    cache = load_json(GEO_CACHE)
    if ip in cache: return cache[ip]
    try:
        import urllib.request
        url = "http://ip-api.com/json/" + ip + "?fields=country,regionName,city,lat,lon"
        req = urllib.request.Request(url, headers={'User-Agent': 'Ziliaozhan/1.0'})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
            cache[ip] = data
            if len(cache) > 5000:
                keys = list(cache.keys())[-3000:]
                cache = {k: cache[k] for k in keys}
            save_json(GEO_CACHE, cache)
            return data
    except: pass
    return {}

def parse_line(line):
    m = re.search(r'^(\S+) .* \[(.+?)\] "\S+ (\S+)', line)
    if not m: return None
    ip, ts_str, path = m.group(1), m.group(2), m.group(3)
    try:
        ts = datetime.strptime(ts_str.split()[0], '%d/%b/%Y:%H:%M:%S')
    except: return None
    if path.startswith('/api/') or path == '/favicon.ico': return None
    if path.startswith('/admin/') or path.startswith('/theme'): return None
    if re.match(r'^/\d{3}$', path): return None
    return {'ip': ip, 'date': ts.strftime('%Y-%m-%d'), 'week': ts.strftime('%Y-W%W'), 'month': ts.strftime('%Y-%m'), 'year': ts.strftime('%Y'), 'path': path, 'hour': ts.hour}

def build():
    logs = []
    for f in sorted(Path(LOG_DIR).glob('access.log*')):
        opener = gzip.open if f.suffix == '.gz' else open
        try:
            with opener(f, 'rt', errors='ignore') as fh:
                for line in fh:
                    p = parse_line(line)
                    if p: logs.append(p)
        except: pass

    daily = defaultdict(lambda: {'views':0,'ips':set()})
    weekly = defaultdict(lambda: {'views':0,'ips':set()})
    monthly = defaultdict(lambda: {'views':0,'ips':set()})
    yearly = defaultdict(lambda: {'views':0,'ips':set()})
    paths = defaultdict(int)
    ip_hours = defaultdict(lambda: defaultdict(int))
    all_ips = set()

    for l in logs:
        daily[l['date']]['views'] += 1; daily[l['date']]['ips'].add(l['ip'])
        weekly[l['week']]['views'] += 1; weekly[l['week']]['ips'].add(l['ip'])
        monthly[l['month']]['views'] += 1; monthly[l['month']]['ips'].add(l['ip'])
        yearly[l['year']]['views'] += 1; yearly[l['year']]['ips'].add(l['ip'])
        paths[l['path']] += 1; all_ips.add(l['ip'])

    def fmt(d):
        return [{'period': k, 'views': v['views'], 'unique': len(v['ips'])} for k, v in sorted(d.items())]

    # Geo data: sample unique IPs
    unique_ip_list = list(set(l['ip'] for l in logs))
    geo_data = []
    sampled = unique_ip_list[:200] if len(unique_ip_list) > 200 else unique_ip_list
    for ip in sampled:
        g = ip_to_geo(ip)
        if g.get('lat') and g.get('lon'):
            geo_data.append({
                'ip': ip[:8] + '***',
                'city': g.get('city',''),
                'region': g.get('regionName',''),
                'country': g.get('country',''),
                'lat': g['lat'], 'lon': g['lon']
            })

    # Province aggregation
    province_views = defaultdict(int)
    for g in geo_data:
        r = g.get('region','')
        if r and g.get('country','') == 'China':
            province_views[r] += 1
    province_list = [{'name': k, 'views': v} for k, v in sorted(province_views.items(), key=lambda x: -x[1])]

    result = {
        'daily': fmt(daily), 'weekly': fmt(weekly),
        'monthly': fmt(monthly), 'yearly': fmt(yearly),
        'topPages': [{'path': p, 'views': c} for p, c in sorted(paths.items(), key=lambda x: -x[1])[:15]],
        'totalViews': len(logs), 'totalIPs': len(all_ips),
        'geoData': geo_data,
        'provinces': province_list,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    with open(CACHE_FILE, 'w') as f:
        json.dump(result, f, ensure_ascii=False)
    return result

def serve():
    print('Content-Type: application/json')
    print()
    if os.path.exists(CACHE_FILE):
        try:
            age = time.time() - os.path.getmtime(CACHE_FILE)
            if age < CACHE_TTL:
                with open(CACHE_FILE) as f:
                    print(f.read())
                return
        except: pass
    data = build()
    print(json.dumps(data, ensure_ascii=False))

serve()
