#!/usr/bin/env python3
"""Integration test: build, validate, check key pages exist."""
import sys
from pathlib import Path

SITE = Path("/var/www/materials")

def check(path, label):
    if path.exists():
        print(f"  OK  {label}: {path.stat().st_size} bytes")
        return True
    print(f"  FAIL {label}: MISSING")
    return False

def main():
    ok = True
    print("Checking generated pages...")
    ok &= check(SITE / "index.html", "Homepage")
    ok &= check(SITE / "cat/study.html", "Category: study")
    ok &= check(SITE / "cat/history.html", "Category: history")
    ok &= check(SITE / "study/gaokao/index.html", "Subpage: gaokao")
    ok &= check(SITE / "study/kaoyan/index.html", "Subpage: kaoyan")
    ok &= check(SITE / "files.json", "File index")

    print()
    print("Checking validation...")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SITE / "site_builder.py"), "--validate"],
        capture_output=True, text=True, cwd=str(SITE)
    )
    print(result.stdout)
    if result.returncode != 0:
        print("  FAIL Validation failed")
        ok = False

    print()
    if ok:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1

if __name__ == "__main__":
    sys.exit(main())
