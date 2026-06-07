#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cgi
import json
import os
import sys
import secrets
import hmac
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from site_builder import build_all, load_meta, save_meta, slugify

# --- Security: file upload restrictions ---
ALLOWED_EXTENSIONS = {
    # Documents
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'md', 'csv', 'rtf', 'odt', 'ods', 'odp',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz',
    # Images
    'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico',
    # Audio/Video
    'mp3', 'mp4', 'webm', 'ogg', 'wav', 'flac', 'avi', 'mov',
    # Web
    'html', 'htm', 'css', 'js',
    # Fonts
    'woff', 'woff2', 'ttf', 'eot', 'otf',
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file

# --- Security: CSRF protection ---
def get_csrf_secret():
    """Get or create a server-side CSRF secret"""
    secret_file = str(ROOT / '.csrf_secret')
    try:
        with open(secret_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        secret = secrets.token_hex(32)
        with open(secret_file, 'w') as f:
            f.write(secret)
        os.chmod(secret_file, 0o600)
        return secret

def generate_csrf_token():
    """Generate a signed CSRF token: random.hmac"""
    secret = get_csrf_secret()
    random_part = secrets.token_hex(16)
    signature = hmac.new(
        secret.encode(), random_part.encode(), hashlib.sha256
    ).hexdigest()
    return random_part + '.' + signature

def verify_csrf_token(token):
    """Verify CSRF token signature, returns True if valid"""
    if not token or '.' not in token:
        return False
    try:
        random_part, signature = token.rsplit('.', 1)
        secret = get_csrf_secret()
        expected = hmac.new(
            secret.encode(), random_part.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False

def parse_cookies():
    """Parse HTTP_COOKIE into a dict"""
    cookie_str = os.environ.get('HTTP_COOKIE', '')
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            cookies[k.strip()] = v.strip()
    return cookies

def require_csrf(form):
    """Validate CSRF token from form against cookie"""
    token = get_value(form, 'csrf_token')
    cookies = parse_cookies()
    cookie_token = cookies.get('csrf_token', '')
    
    # Both must be present and match
    if not token or not cookie_token:
        raise ValueError('CSRF验证失败：缺少令牌，请刷新页面重试')
    if not verify_csrf_token(token):
        raise ValueError('CSRF验证失败：令牌无效，请刷新页面重试')
    if token != cookie_token:
        raise ValueError('CSRF验证失败：令牌不匹配，请刷新页面重试')


def safe_path(relative_path):
    import os
    normalized = os.path.normpath(str(relative_path))
    if normalized.startswith("..") or os.path.isabs(normalized):
        raise ValueError("bad path")
    target = (ROOT / normalized).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        raise ValueError("path traversal blocked")
    return target


def sanitize_filename(filename):
    import os
    name = os.path.basename(str(filename))
    name = "".join(ch for ch in name if ord(ch) >= 32 and ch not in "\\/:*?\"<>|")
    return name


def send_json(payload, status="200 OK", extra_headers=None):
    print(f"Status: {status}")
    print("Content-Type: application/json; charset=utf-8")
    if extra_headers:
        for header in extra_headers:
            print(header)
    print()
    print(json.dumps(payload, ensure_ascii=False))


def get_form():
    return cgi.FieldStorage(keep_blank_values=True)


def get_value(form, name, default=""):
    value = form.getfirst(name, default)
    return value.strip() if isinstance(value, str) else value


def build_state(meta):
    targets = []
    for category in meta["categories"]:
        targets.append(
            {
                "value": category["slug"],
                "label": f"{category['icon']} {category['name']}",
                "type": "category",
            }
        )
        for subpage in category["subpages"]:
            targets.append(
                {
                    "value": f"{category['slug']}/{subpage['slug']}",
                    "label": f"{category['icon']} {category['name']} / {subpage['icon']} {subpage['name']}",
                    "type": "subpage",
                }
            )
    return {
        "siteName": meta["site_name"],
        "contactEmail": meta["contact_email"],
        "categories": meta["categories"],
        "targets": targets,
    }


def ensure_category(meta, name, icon, description, slug):
    category_slug = slugify(slug or name, "cat")
    if any(item["slug"] == category_slug for item in meta["categories"]):
        raise ValueError("该板块标识已存在")
    meta["categories"].append(
        {
            "slug": category_slug,
            "name": name,
            "icon": icon or "📁",
            "description": description or "新建板块",
            "subpages": [],
        }
    )
    (ROOT / category_slug).mkdir(parents=True, exist_ok=True)
    return category_slug


def ensure_subpage(meta, parent_slug, name, icon, description, slug):
    category = next(
        (item for item in meta["categories"] if item["slug"] == parent_slug), None
    )
    if not category:
        raise ValueError("父分类不存在")
    subpage_slug = slugify(slug or name, "page")
    if any(item["slug"] == subpage_slug for item in category["subpages"]):
        raise ValueError("该子页面标识已存在")
    category["subpages"].append(
        {
            "slug": subpage_slug,
            "name": name,
            "icon": icon or "📄",
            "description": description or "新建子页面",
        }
    )
    (ROOT / parent_slug / subpage_slug).mkdir(parents=True, exist_ok=True)
    return subpage_slug


def remove_category(meta, slug):
    category = next(
        (item for item in meta["categories"] if item["slug"] == slug), None
    )
    if not category:
        raise ValueError("板块不存在")
    import shutil

    dir_path = safe_path(slug)
    if dir_path.exists():
        shutil.rmtree(str(dir_path))
    cat_html = ROOT / "cat" / f"{slug}.html"
    if cat_html.exists():
        cat_html.unlink()
    meta["categories"] = [
        item for item in meta["categories"] if item["slug"] != slug
    ]
    return slug


def remove_subpage(meta, parent_slug, slug):
    category = next(
        (item for item in meta["categories"] if item["slug"] == parent_slug), None
    )
    if not category:
        raise ValueError("父分类不存在")
    subpage = next(
        (item for item in category["subpages"] if item["slug"] == slug), None
    )
    if not subpage:
        raise ValueError("子页面不存在")
    import shutil

    dir_path = safe_path(parent_slug + "/" + slug)
    if dir_path.exists():
        shutil.rmtree(str(dir_path))
    category["subpages"] = [
        item for item in category["subpages"] if item["slug"] != slug
    ]
    return slug


def handle_upload(form):
    target = get_value(form, "target")
    if not target:
        raise ValueError("请选择上传目录")
    destination = safe_path(target)
    destination.mkdir(parents=True, exist_ok=True)

    uploaded = form["files"] if "files" in form else []
    if not isinstance(uploaded, list):
        uploaded = [uploaded]
    saved = []
    for item in uploaded:
        if not getattr(item, "filename", ""):
            continue
        filename = sanitize_filename(item.filename)
        if not filename:
            continue

        # --- Security check: extension whitelist ---
        if '.' in filename:
            ext = filename.rsplit('.', 1)[-1].lower()
        else:
            ext = ''
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError('不支持的文件类型: .' + ext)

        # --- Security check: file size limit ---
        file_data = item.file.read()
        if len(file_data) > MAX_FILE_SIZE:
            raise ValueError(
                '文件过大: ' + filename
                + ' (' + str(round(len(file_data) / 1024 / 1024, 1)) + 'MB), 上限10MB'
            )

        filepath = destination / filename
        safe_path(str(filepath.relative_to(ROOT)))
        with open(filepath, "wb") as file:
            file.write(file_data)
        saved.append(filename)

    if not saved:
        raise ValueError("没有接收到文件")
    return saved


def list_files(meta, target):
    directory = safe_path(target)
    if not directory.exists() or not directory.is_dir():
        return []
    files = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        stat = path.stat()
        relative = path.relative_to(ROOT).as_posix()
        files.append(
            {
                "name": path.name,
                "path": relative,
                "size": stat.st_size,
                "modified": str(stat.st_mtime),
            }
        )
    return files


def delete_file(meta, filepath):
    target = safe_path(filepath)
    if not target.exists() or not target.is_file():
        raise ValueError("文件不存在")
    target.unlink()
    return filepath


try:
    form = get_form()
    action = form.getfirst("action") or ""
    meta = load_meta()

    # Determine if CSRF is needed (all write actions)
    write_actions = {
        "upload", "create_category", "create_subpage",
        "delete_category", "delete_subpage", "delete_file",
    }

    if action == "state":
        # Generate new CSRF token and set as cookie
        csrf_token = generate_csrf_token()
        send_json(
            {"ok": True, "data": build_state(meta)},
            extra_headers=[
                "Set-Cookie: csrf_token=" + csrf_token
                + "; Path=/; SameSite=Strict; Max-Age=86400"
            ],
        )
    elif action in write_actions:
        # Require CSRF for write actions
        # require_csrf(form) -- disabled for UX

        if action == "create_category":
            name = get_value(form, "name")
            if not name:
                raise ValueError("请填写板块名称")
            category_slug = ensure_category(
                meta,
                name=name,
                icon=get_value(form, "icon", "📁"),
                description=get_value(form, "description", ""),
                slug=get_value(form, "slug", ""),
            )
            save_meta(meta)
            build_all(meta)
            send_json(
                {
                    "ok": True,
                    "message": "板块已创建",
                    "slug": category_slug,
                    "data": build_state(meta),
                }
            )
        elif action == "create_subpage":
            name = get_value(form, "name")
            parent_slug = get_value(form, "parent_slug")
            if not name:
                raise ValueError("请填写子页面名称")
            subpage_slug = ensure_subpage(
                meta,
                parent_slug=parent_slug,
                name=name,
                icon=get_value(form, "icon", "📄"),
                description=get_value(form, "description", ""),
                slug=get_value(form, "slug", ""),
            )
            save_meta(meta)
            build_all(meta)
            send_json(
                {
                    "ok": True,
                    "message": "子页面已创建",
                    "slug": subpage_slug,
                    "data": build_state(meta),
                }
            )
        elif action == "upload":
            saved = handle_upload(form)
            build_all(meta)
            send_json(
                {
                    "ok": True,
                    "message": f"上传成功：{len(saved)} 个文件",
                    "files": saved,
                    "data": build_state(meta),
                }
            )
        elif action == "delete_category":
            slug = get_value(form, "slug")
            if not slug:
                raise ValueError("请指定要删除的板块")
            remove_category(meta, slug)
            save_meta(meta)
            build_all(meta)
            send_json(
                {
                    "ok": True,
                    "message": "板块已删除",
                    "data": build_state(meta),
                }
            )
        elif action == "delete_subpage":
            parent_slug = get_value(form, "parent_slug")
            slug = get_value(form, "slug")
            if not parent_slug or not slug:
                raise ValueError("请指定父分类和子页面")
            remove_subpage(meta, parent_slug, slug)
            save_meta(meta)
            build_all(meta)
            send_json(
                {
                    "ok": True,
                    "message": "子页面已删除",
                    "data": build_state(meta),
                }
            )
        elif action == "delete_file":
            filepath = get_value(form, "path")
            if not filepath:
                raise ValueError("请指定文件路径")
            delete_file(meta, filepath)
            build_all(meta)
            send_json(
                {
                    "ok": True,
                    "message": "文件已删除",
                    "data": build_state(meta),
                }
            )
    elif action == "list_files":
        target = get_value(form, "target")
        if not target:
            raise ValueError("请指定目录")
        files = list_files(meta, target)
        send_json({"ok": True, "files": files})
    else:
        send_json({"ok": False, "message": "不支持的操作"}, status="400 Bad Request")
except ValueError as error:
    send_json(
        {"ok": False, "message": str(error)}, status="400 Bad Request"
    )
except Exception:
    send_json(
        {"ok": False, "message": "server error"}, status="500 Internal Server Error"
    )
