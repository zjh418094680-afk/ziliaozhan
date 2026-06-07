#!/bin/bash
# Training 4: CI Pipeline Script
# Stages: lint -> test -> build -> deploy
# Each stage can fail independently with clear reporting.
# Usage: ./ci.sh [stage]   (default: all)
#        ./ci.sh --help

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
START_TIME=$(date +%s)

stage_header() {
    echo ""
    echo -e "${YELLOW}═══ $1 ═══${NC}"
}

stage_pass() {
    echo -e "  ${GREEN}PASS${NC} $1"
    PASS=$((PASS + 1))
}

stage_fail() {
    echo -e "  ${RED}FAIL${NC} $1 — $2"
    FAIL=$((FAIL + 1))
}

stage_skip() {
    echo -e "  ${YELLOW}SKIP${NC} $1 — $2"
    SKIP=$((SKIP + 1))
}

summary() {
    local elapsed=$(($(date +%s) - START_TIME))
    echo ""
    echo "════════════════════════════════════"
    echo "  CI Summary: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped (${elapsed}s)"
    echo "════════════════════════════════════"
    if [ "$FAIL" -gt 0 ]; then
        exit 1
    fi
}

# ── Stage: Lint/Validate ──
run_lint() {
    stage_header "LINT"
    
    # Check for Python syntax errors
    local py_ok=true
    for f in $(find . -name '*.py' -not -path './.git/*' -not -path './venv/*' 2>/dev/null); do
        if ! python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null; then
            python3 -m py_compile "$f" 2>&1 || py_ok=false
        fi
    done
    if $py_ok; then
        stage_pass "Python syntax check"
    else
        stage_fail "Python syntax check" "compile errors found"
    fi
    
    # Check for common anti-patterns in generated HTML
    if [ -f "site_builder.py" ]; then
        if python3 site_builder.py --validate 2>&1; then
            stage_pass "Site builder validation"
        else
            stage_fail "Site builder validation" "ES6 violations found"
        fi
    else
        stage_skip "Site builder validation" "no site_builder.py found"
    fi
    
    # Check git status (no uncommitted changes in generated files)
    if git rev-parse --git-dir > /dev/null 2>&1; then
        if git diff --quiet -- '*.html' 2>/dev/null; then
            stage_pass "Generated HTML matches committed"
        else
            stage_fail "Generated HTML matches committed" "uncommitted changes in HTML files"
        fi
    else
        stage_skip "Git status check" "not a git repo"
    fi
}

# ── Stage: Test ──
run_test() {
    stage_header "TEST"
    
    # Run Python tests if test file exists
    if [ -f "test_site.py" ]; then
        if python3 test_site.py 2>&1; then
            stage_pass "Integration tests"
        else
            stage_fail "Integration tests" "test failures"
        fi
    else
        stage_skip "Integration tests" "no test_site.py found"
    fi
    
    # Run API tests if exists
    if [ -f "training/api.py" ]; then
        if python3 training/api.py --test 2>&1; then
            stage_pass "API unit tests"
        else
            stage_fail "API unit tests" "test failures"
        fi
    else
        stage_skip "API unit tests" "no api.py found"
    fi
}

# ── Stage: Build ──
run_build() {
    stage_header "BUILD"
    
    if [ -f "site_builder.py" ]; then
        if python3 site_builder.py --build 2>&1; then
            stage_pass "Site builder"
        else
            stage_fail "Site builder" "build failed"
        fi
    else
        stage_skip "Site builder" "no site_builder.py found"
    fi
}

# ── Stage: Deploy ──
run_deploy() {
    stage_header "DEPLOY"
    
    # Check if we have a deploy target
    if [ -n "${DEPLOY_TARGET:-}" ]; then
        echo "  Deploying to ${DEPLOY_TARGET}..."
        if rsync -avz --delete ./ "root@${DEPLOY_TARGET}:/var/www/materials/" 2>&1; then
            stage_pass "Deploy to ${DEPLOY_TARGET}"
        else
            stage_fail "Deploy to ${DEPLOY_TARGET}" "rsync failed"
        fi
    else
        stage_skip "Deploy" "DEPLOY_TARGET not set"
    fi
    
    # Git push as deploy alternative
    if git rev-parse --git-dir > /dev/null 2>&1; then
        local branch=$(git rev-parse --abbrev-ref HEAD)
        if git push origin "$branch" 2>&1; then
            stage_pass "Git push to origin/$branch"
        else
            stage_fail "Git push" "push failed"
        fi
    fi
}

# ── Main ──
if [ "${1:-}" == "--help" ] || [ "${1:-}" == "-h" ]; then
    echo "CI Pipeline Script"
    echo "Usage: ./ci.sh [stage]"
    echo "Stages: lint, test, build, deploy, all (default)"
    exit 0
fi

STAGE="${1:-all}"

case "$STAGE" in
    lint)   run_lint; summary ;;
    test)   run_test; summary ;;
    build)  run_build; summary ;;
    deploy) run_deploy; summary ;;
    all)
        run_lint
        run_test
        run_build
        run_deploy
        summary
        ;;
    *)
        echo "Unknown stage: $STAGE"
        echo "Valid: lint, test, build, deploy, all"
        exit 2
        ;;
esac
