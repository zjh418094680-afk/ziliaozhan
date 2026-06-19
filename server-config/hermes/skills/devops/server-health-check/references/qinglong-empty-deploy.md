# Qinglong (青龙) Empty-Deploy Check

Symptom: user says "I deployed JD scripts but nothing happens."

## Quick Check

```bash
# Container status
docker ps -a --filter name=qinglong

# Mount point (where data lives)
docker inspect qinglong --format '{{.HostConfig.Binds}}'
```

## API Checks (authenticated)

Get a token first:
```bash
TOKEN=$(curl -s http://localhost:5700/api/user/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")
```

Then check the three things that must all be present for JD scripts to work:

| Endpoint | What it tells you | Required for scripts to work |
|----------|-------------------|----------------------------|
| `/api/crons` | Scheduled tasks | Must be non-empty |
| `/api/envs` | Environment variables (JD_COOKIE etc.) | Must contain `JD_COOKIE` |
| `/api/scripts` | Script files pulled from repos | Must have actual JD scripts, not just samples |

## Filesystem Check

```bash
ls /root/qinglong/data/scripts/    # should have more than sample files
ls /root/qinglong/data/repo/       # should have cloned script repos
```

## Root Causes for "Deployed but Not Working"

1. **No script repos pulled** — `repo/` is empty, only default `ql_sample.js` etc. exist
2. **No JD_COOKIE set** — environment variables are empty
3. **No cron jobs created** — scripts exist but never run on schedule

## Setup: Full JD Script Deployment (When Empty Deploy Diagnosed)

Use when the user wants to go from empty qinglong to working JD scripts.

### JD Cookie Format

**⚠️ Modern JD (2026) requires App-level cookies — browser cookies from `m.jd.com` are NOT enough.**

Minimum working Cookie:
```
pt_key=<long-hex-string>;pt_pin=jd_<username>;wskey=<hex>;pin=jd_<username>;
```

| Field | Source | Required? |
|-------|--------|-----------|
| `pt_key` | `m.jd.com` browser | ✅ Always |
| `pt_pin` | `m.jd.com` browser | ✅ Always |
| `wskey` | JD App packet capture | ✅ **Critical** — without it, scripts fail with "H5ST 失败" / "进入活动失败" |
| `pin` | JD App packet capture | ✅ Often needed |
| `appid` / `wsAppid` | JD App packet capture | Optional but helps |

**Why browser cookies fail:** CK detection will show "状态正常" because `pt_key` is valid for basic auth, but modern JD API endpoints require `wskey`+`pin` for H5ST signing. The scripts will hit "获取 H5ST 失败" or "活动太火爆" — this is NOT a script bug, it's a cookie completeness problem.

### How to Get Complete Cookies

**iPhone (Stream App):**
1. App Store → download **Stream**
2. Settings → HTTPS抓包 → Install CA Certificate → follow system prompts
3. Settings → General → About → Certificate Trust Settings → enable Stream
4. Start capture → open JD App → browse activity pages → stop capture
5. Find any request to `api.m.jd.com` → Request Headers → copy the full `Cookie` string

**Android:**
1. Download **抓包大师** or **HttpCanary**
2. Install CA certificate (same pattern as iOS)
3. Capture JD App traffic → copy full Cookie from any `api.m.jd.com` request

The captured Cookie will be much longer than the browser version — it includes `wskey`, `pin`, `appid`, and many other fields. Paste the complete string as the `JD_COOKIE` environment variable value.

**Legacy (browser-only, insufficient for most scripts):**
```
pt_key=<long-hex-string>;pt_pin=jd_<username>;
```
- User gets this from `m.jd.com` → F12 → Application → Cookies → copy `pt_key` and `pt_pin` values
- Must use mobile site `m.jd.com`, NOT `www.jd.com`
- Multiple accounts separated by `&`

### Pulling Script Repos Behind a China Proxy

When GitHub is blocked and git gets 401 through proxy:
1. `curl -L --proxy http://127.0.0.1:7890 -o /tmp/repo.tar.gz "https://api.github.com/repos/<owner>/<repo>/tarball/main"`
2. `tar xzf /tmp/repo.tar.gz && mv <extracted-dir> faker3_repo`
3. `docker cp faker3_repo qinglong:/ql/data/repo/<name>`
4. Copy scripts manually: `docker exec qinglong bash -c 'cp /ql/data/repo/<name>/*.js /ql/data/scripts/'`

**Pitfall:** `host.docker.internal` only works on Docker Desktop (macOS/Windows). On Linux, the Docker bridge gateway is `172.17.0.1` — get it with `docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}'`.

### Dependency Copying (Manual Repo Setup)

When `ql repo` doesn't work (no git access), copy everything manually:

```bash
# 1. Copy the tarballed repo into the container (see "Pulling Script Repos" above)

# 2. Copy scripts AND all dependencies into /ql/data/scripts/
docker exec qinglong bash -c '
SRC=/ql/data/repo/faker3
DST=/ql/data/scripts

# Core modules — REQUIRED, not optional
cp "$SRC/jdCookie.js" "$DST/"
cp "$SRC/sendNotify.js" "$DST/"
cp "$SRC/ql.js" "$DST/"

# Dependency directories — REQUIRED for modern scripts
for dir in utils function backUp; do
  [ -d "$SRC/$dir" ] && cp -r "$SRC/$dir" "$DST/"
done

# Then copy the actual script files
for f in "$SRC"/jd_*.js "$SRC"/jx_*.js; do
  [ -f "$f" ] && cp "$f" "$DST/"
done
'
```

**Critical:** `jdCookie.js`, `utils/`, and `function/` MUST be copied. Without them, scripts fail with `MODULE_NOT_FOUND` errors. The shared module `utils/Rebels_sendJDNotify.js` is a common missing dependency.

### Dependencies (npm)
```bash
docker exec qinglong bash -c '
export HTTP_PROXY=http://172.17.0.1:7890
export HTTPS_PROXY=http://172.17.0.1:7890
# got@13 is ESM-only, pin to got@11 for CJS compatibility
npm install -g got@11 tough-cookie jsdom crypto-js date-fns request axios moment --registry=https://registry.npmmirror.com
'
```

**Dependency notes:**
- `got@11` (not `got@latest`) — got@13+ is ESM-only and incompatible with CJS `require()` used by JD scripts
- `moment` — required by `jd_bean_change.js`; will fail with `MODULE_NOT_FOUND` if missing
- If npm install times out without the proxy, retry with `HTTP_PROXY`/`HTTPS_PROXY` set

### Environment Variable (JD_COOKIE)

Write via API:
```bash
curl -s -X POST http://localhost:5700/api/envs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '[{"name":"JD_COOKIE","value":"pt_key=...;pt_pin=...;","remarks":"主号"}]'
```

### Cron Jobs

Standard gold-bean schedule (create via API):
| Script | Schedule | Purpose |
|--------|----------|---------|
| `task jd_bean_home.js` | `0 0,6,9,12,16,20,22 * * *` | Collect gold beans |
| `task jd_plantBean.js` | `0 7 * * *` | Plant beans |
| `task jd_fruit_new.js` | `0 8 * * *` | JD Farm |
| `task jd_daka_bean.js` | `0 9 * * *` | Check-in beans |
| `task jd_signbeanact_.js` | `0 10 * * *` | Sign-in beans |
| `task jd_CheckCK.js` | `0 2 * * *` | Cookie validity check |
| `task jd_bean_change.js` | `0 20 * * *` | Bean change notification |

**API gotcha:** Individual cron creation expects `{"name":"...","command":"...","schedule":"..."}` — NOT wrapped in `{"data": [...]}`.

**Verification:**
```bash
docker exec qinglong python3 -c "
import sqlite3
conn = sqlite3.connect('/ql/data/db/database.sqlite')
rows = conn.execute('SELECT name,command,schedule FROM Crontabs').fetchall()
print(f'Total: {len(rows)} cron jobs')
for r in rows: print(f'  {r[0]:14s} {r[1]:30s} {r[2]}')
"
```

### Test Run & H5ST Diagnosis

After setup, test one script manually:
```bash
docker exec qinglong task jd_bean_home.js
```

**Expected outcomes:**
- ✅ `"状态正常!"` / actual bean count returned — Cookie valid, script working. Setup complete.
- ⚠️ `"获取 H5ST 失败"` / `"活动太火爆"` — Can be EITHER incomplete Cookie OR the script's H5ST algorithm being outdated. See diagnosis below.
- ❌ `"Cannot find module './jdCookie'"` — dependencies not copied. Re-run the Dependency Copying step.

### H5ST Diagnosis — Two Possible Root Causes

"获取 H5ST 失败" or "活动太火爆" has two distinct causes:

1. **Incomplete Cookie (missing `wskey`/`pin`):** The most common cause. Browser cookies from `m.jd.com` lack fields needed for H5ST signing. Fix: get App-level cookies via Stream/抓包大师.

2. **Outdated script H5ST algorithm (Cookie IS complete):** Even with full App cookies, the script's embedded H5ST generation may be out of sync with JD's current algorithm. This is a cat-and-mouse game — JD updates weekly, open-source scripts lag behind.

**How to tell which:** Run `jd_bean_change.js` (asset stats) — it uses simpler APIs that rarely require H5ST. If it returns real data (bean count, Plus status, wallet balance) but `jd_bean_home.js` still fails, the Cookie is complete and the problem is the script's H5ST algorithm.

**Systematic compatibility test:** After setup, run scripts one at a time to identify which work and which don't:

```bash
docker exec qinglong task jd_CheckCK.js       # Cookie validity — should pass
docker exec qinglong task jd_bean_change.js    # Asset stats — simple API, decider test
docker exec qinglong task jd_signbeanact_.js   # Daily sign-in — often works
docker exec qinglong task jd_bean_home.js      # Gold bean collector — H5ST-heavy, may fail
docker exec qinglong task jd_plantBean.js      # Plant beans — may fail
docker exec qinglong task jd_fruit_new.js      # JD Farm — may fail
```

| Script | API complexity | Typical failure mode |
|--------|---------------|---------------------|
| `jd_CheckCK.js` | Auth check | Cookie expired |
| `jd_bean_change.js` | Simple query | Missing npm deps (`moment`) |
| `jd_signbeanact_.js` | Simple POST | Cookie incomplete |
| `jd_bean_home.js` | Complex, H5ST-heavy | H5ST algorithm mismatch |
| `jd_plantBean.js` | Complex | "进入活动失败" |
| `jd_fruit_new.js` | Complex | "活动太火爆" |

**Cookie check only proves basic validity, not script compatibility.** A `pt_key` that passes CK detection can still fail every actual JD activity script — either because `wskey` is missing OR because the script's H5ST algorithm is stale.

### Common Pitfalls

- **Cookie expires in 1-2 days** — user must re-capture periodically
- **git gets 401 through proxy while curl works** — download tarball directly, skip git
- **`ql repo` command won't work without git** — do everything manually (copy scripts, install deps, create crons)
- **Crontabs table name** — it's `Crontabs` (not `crons`) in qinglong's SQLite database
