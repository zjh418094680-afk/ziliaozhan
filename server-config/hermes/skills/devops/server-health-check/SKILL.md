---
name: server-health-check
description: Diagnose Linux server health and clean up junk.
version: 1.0.0
author: Hermes Agent
tags: [devops, linux, diagnostics, cleanup]
---

# Server Health Check Skill

Systematic diagnosis of Linux server health — find failures, conflicts, resource pressure, and junk. Non-destructive by default; only act on the user's explicit go-ahead.

## When to Use

- User asks "what's wrong with my server" or "check server health"
- After a server reboot or migration — verify everything came back clean
- Periodic maintenance — catch failing services and disk pressure early

## Prerequisites

- Shell access (root or sudo) on the target server
- Standard Linux tools: `df`, `free`, `uptime`, `top`, `ss`, `systemctl`, `journalctl`, `dpkg`/`apt`, `docker` (if used)

## Procedure

### Phase 1 — Quick Surface Scan (parallel)

Run these simultaneously — they're all read-only and independent:

```
df -h                           # disk usage
free -h                         # memory
uptime                          # load + uptime
cat /proc/loadavg               # raw load
systemctl list-units --state=failed   # failed units
```

### Phase 2 — Deep Inspection

```
top -b -n 1 -o %CPU | head -20  # top processes
ss -tlnp                         # listening ports
journalctl --no-pager -p 3 -xb | tail -30  # system errors
apt list --upgradable             # pending updates (Ubuntu/Debian)
uname -r && ls /boot/vmlinuz*     # kernel version + old kernels
docker ps -a                      # containers (if docker present)
```

### Phase 3 — Service Failure Root Cause

For each failed service found in Phase 1:
1. `systemctl status <svc> --no-pager` — read the exit code and error message
2. `systemctl cat <svc>` — inspect the unit file for missing paths, deps, env vars
3. Check if WorkingDirectory, ExecStart paths, and log paths actually exist on disk

Common causes:
- **status=209/STDOUT** → `StandardOutput`/`StandardError` path doesn't exist (missing `logs/` dir is the usual suspect)
- **status=203/EXEC** → the `ExecStart` binary doesn't exist
- **status=200/CHDIR** → `WorkingDirectory` doesn't exist

### Phase 4 — Nginx Config Conflicts

In `/etc/nginx/sites-enabled/`, nginx loads ALL files — including `.bak` copies. If the same `server_name` appears in multiple files, you get "conflicting server name" warnings and unpredictable behavior.

```
nginx -t 2>&1                          # check for conflicts
ls /etc/nginx/sites-enabled/           # list active configs
```

Move `.bak` files OUT of sites-enabled (they belong in a backup directory, not nginx's active config path).

### Phase 5 — Junk File Cleanup

Look in `/root/` and other home directories for:
- Zero-length files with meaningless names
- Filenames with special characters (newlines, brackets, non-ASCII) — these are almost always script trash
- Empty directories left behind by removed services

**For files with special characters:** `ls -i` to get inode numbers, then `find . -maxdepth 1 -inum <N> -delete`. Don't try to quote or escape — inode deletion bypasses the filename entirely.

## Pitfalls

- **Never delete without the user's go-ahead** — always present findings, then act on explicit approval.
- **Don't touch websites, databases, or user data** unless the user explicitly asks. Default posture: check everything, suggest cleanup, act only on confirmed junk.
- **nginx sites-enabled loads ALL files in the directory alphabetically** — a `.bak` file IS an active config, not a backup. Move it out, don't leave it there.
- **`systemctl` may list 0 failed units even when a service is crash-looping** if it's stuck in `activating (auto-restart)`. Cross-check with `journalctl -p 3`.
- **Files with special characters (brackets, newlines, non-ASCII) can't be deleted by name** — use `ls -i` to get inode, then `find . -maxdepth 1 -inum <N> -delete`.
- **`host.docker.internal` only works on Docker Desktop (macOS/Windows)** — on Linux, the Docker bridge gateway is at `172.17.0.1`. Use `docker network inspect bridge` to confirm.
- **Qinglong empty deploy:** see `references/qinglong-empty-deploy.md` for diagnosis AND full setup workflow (JD scripts behind China proxy). Quick decider: `docker exec qinglong task jd_bean_change.js` — if it returns real bean counts but `jd_bean_home.js` fails with H5ST errors, the Cookie is complete and the script's H5ST algorithm is just outdated.
- **Git auto-backup via cron:** see `references/git-auto-backup.md` for the pattern of backing up server projects to GitHub on a schedule using `no_agent=true` Hermes cron jobs with git SSH. Covers `--no-verify` for pre-commit hooks, `safe.directory` for cross-user repos, and ETag-based update polling for upstream script repos.

## Verification

After cleanup, confirm:
- `systemctl list-units --state=failed` returns 0
- `nginx -t` shows zero warnings
- `df -h` and `free -h` show acceptable levels
- No more repeating errors in `journalctl -p 3`
