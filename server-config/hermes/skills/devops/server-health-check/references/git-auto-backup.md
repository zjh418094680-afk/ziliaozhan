# Git Auto-Backup via Hermes Cron

Pattern for automatically backing up server projects to GitHub using git SSH + Hermes cron.

## When to Use

- User has local git repos they want auto-pushed to GitHub on a schedule
- Server projects that change over time (websites, configs) need disaster recovery
- Want versioned snapshots without remembering to commit/push manually

## Script Template

```bash
#!/bin/bash
# Server project auto-backup to GitHub
set -e
export HOME=/root
LOG_FILE="/var/log/auto_backup.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

REPO_DIR="/path/to/project"
GIT_MSG="auto: $(date +%Y-%m-%d_%H:%M)"

cd "$REPO_DIR"
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

# Sync server configs into the repo if desired
mkdir -p server-config/nginx
rsync -a --delete /etc/nginx/sites-enabled/ server-config/nginx/sites-enabled/ 2>/dev/null || true
cp /etc/nginx/nginx.conf server-config/nginx/nginx.conf 2>/dev/null || true

git add -A 2>/dev/null || true

if git diff --cached --quiet; then
    log "  ✓ no changes"
else
    git commit --no-verify -m "$GIT_MSG" 2>&1
    git push origin master 2>&1
    log "  ✓ pushed"
fi
```

## Key Design Decisions

### Use `--no-verify` on commit

Pre-commit hooks (linters, validators) often fail during auto-backup. The goal is to snapshot state, not to pass CI. Use `--no-verify`.

### Use `no_agent=true` cron jobs

Backup scripts are pure shell — no LLM reasoning needed. Use `no_agent=true` so the scheduler runs the script directly without spinning up an agent session. This saves tokens and avoids the 3-minute hard interrupt.

```bash
hermes cron add \
  --name "网站自动备份" \
  --schedule "every 6h" \
  --script "auto_backup.sh" \
  --no_agent
```

### Organize by directory within a single repo

Rather than creating many small GitHub repos, put everything in one repo organized by directory:

```
/
├── index.html          # website source
├── site_builder.py     # build scripts
├── server-config/      # nginx, systemd, etc.
│   └── nginx/
└── templates/          # page templates
```

### ETag-based update detection (for script updates, not git commits)

When polling GitHub for upstream updates (e.g., script repos that don't have local git history), use the ETag header to skip redundant downloads:

```bash
REMOTE_ETAG=$(curl -sI --proxy "$PROXY" -L "$URL" 2>/dev/null | grep -i 'etag:' | tr -d '\r' | head -1)
if [ -f "$LAST_HASH_FILE" ] && [ "$REMOTE_ETAG" = "$(cat $LAST_HASH_FILE)" ]; then
    exit 0  # no update, silent exit
fi
```

## Pitfalls

- **`git config --global --add safe.directory`** is needed when the repo dir is owned by a different user (e.g., `www-data` owns `/var/www/` but root runs the backup)
- **`$HOME` must be set** for git to find `~/.ssh`. Set `export HOME=/root` at the top of the script.
- **Pre-commit hooks will block backups** unless `--no-verify` is used. Don't try to fix the hook — bypass it.
- **fstab and other system files** can accidentally get committed. Add them to `.gitignore` and `git rm --cached` them in the backup script.
- **SSH key must be pre-configured** — `ssh -T git@github.com` should return success before setting up the cron job. Use `gh auth status` if using `gh` CLI.
