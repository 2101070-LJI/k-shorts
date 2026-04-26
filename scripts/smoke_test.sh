#!/usr/bin/env bash
# Quick smoke-test for demo readiness. Run after `uvicorn app.main:app` is up.
set -e
BASE="${API_BASE:-http://localhost:8000}"
PASS=0; FAIL=0

check() {
  local name="$1" expected="$2"
  local actual
  actual=$(curl -sf "$BASE$3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$4','MISSING'))" 2>/dev/null || echo "ERROR")
  if [ "$actual" = "$expected" ]; then
    echo "  PASS  $name"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $name (expected '$expected', got '$actual')"
    FAIL=$((FAIL+1))
  fi
}

post_check() {
  local name="$1" url="$2" body="$3" key="$4"
  local actual
  actual=$(curl -sf -X POST -H 'Content-Type: application/json' -d "$body" "$BASE$url" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$key','MISSING'))" 2>/dev/null || echo "ERROR")
  if [ "$actual" != "ERROR" ] && [ "$actual" != "MISSING" ]; then
    echo "  PASS  $name (got: $actual)"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $name"
    FAIL=$((FAIL+1))
  fi
}

echo "=== K-Shorts Smoke Test ==="
check  "GET /health → ok"        "ok"        /health        status
check  "GET /health → ollama"    "connected" /health        ollama
echo ""
echo "Templates:"
curl -sf "$BASE/templates" | python3 -c "
import sys,json
ts=json.load(sys.stdin)
ids=[t['id'] for t in ts]
print('  ids:', ids)
print('  PASS' if {'clean','soft','bold'}.issubset(set(ids)) else '  FAIL: missing expected templates')
" 2>/dev/null || echo "  FAIL"

echo ""
echo "Weights:"
curl -sf "$BASE/evolution/weights" | python3 -c "
import sys,json
d=json.load(sys.stdin)
w=d['current']
total=sum(w.values())
print(f'  total={total:.3f}  {dict((k,round(v,3)) for k,v in w.items())}')
print('  PASS' if abs(total-1.0)<0.01 else '  FAIL: weights do not sum to 1')
" 2>/dev/null || echo "  FAIL"

echo ""
echo "Fewshot (cold-start OK):"
curl -sf "$BASE/preferences/fewshot" | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'  examples={len(d)} (0 is OK on cold start)')
" 2>/dev/null || echo "  FAIL"

echo ""
echo "─────────────────────────"
echo "  PASSED: $PASS"
echo "  FAILED: $FAIL"
[ "$FAIL" -eq 0 ] && echo "  All clear — demo ready!" || exit 1
