#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
OPENAI_COMPAT_API_KEY="${OPENAI_COMPAT_API_KEY:-EMPTY}"
SMOKE_RUN_CHAT="${SMOKE_RUN_CHAT:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

curl -fsS "${API_BASE_URL}/health" >/dev/null
curl -fsS "${API_BASE_URL}/diagnostics" >/dev/null
curl -fsS \
  -H "Authorization: Bearer ${OPENAI_COMPAT_API_KEY}" \
  "${API_BASE_URL}/v1/models" >/dev/null

AUTH_STATUS="$(
  curl -sS -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer wrong-smoke-key" \
    "${API_BASE_URL}/v1/models"
)"
if [[ "${AUTH_STATUS}" != "401" ]]; then
  echo "expected /v1/models with wrong-smoke-key to return 401, got ${AUTH_STATUS}" >&2
  exit 1
fi

SMOKE_MEMORY_ID="smoke-memory-$(date +%s)"
curl -fsS \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"smoke\",\"project_id\":\"smoke\",\"session_id\":\"${SMOKE_MEMORY_ID}\",\"content\":\"${SMOKE_MEMORY_ID}\",\"memory_type\":\"smoke\",\"title\":\"${SMOKE_MEMORY_ID}\",\"tags\":[\"smoke\"],\"importance\":5}" \
  "${API_BASE_URL}/memory/ingest" >/dev/null

MEMORY_SEARCH_RESPONSE="$(
  curl -fsS \
    "${API_BASE_URL}/memory/search?user_id=smoke&project_id=smoke&query=${SMOKE_MEMORY_ID}&top_k=1"
)"
"${PYTHON_BIN}" - "${MEMORY_SEARCH_RESPONSE}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if not payload.get("results"):
    raise SystemExit("memory ingest smoke returned no search results")
PY

if [[ "${SMOKE_RUN_CHAT}" == "1" ]]; then
  SMOKE_ID="smoke-e2e-$(date +%s)"
  curl -fsS \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"smoke\",\"project_id\":\"smoke\",\"session_id\":\"${SMOKE_ID}\",\"message\":\"${SMOKE_ID}\",\"mode\":\"chat\"}" \
    "${API_BASE_URL}/chat" >/dev/null

  SEARCH_RESPONSE="$(
    curl -fsS \
      "${API_BASE_URL}/memory/search?user_id=smoke&project_id=smoke&query=${SMOKE_ID}&top_k=1"
  )"

  "${PYTHON_BIN}" - "${SEARCH_RESPONSE}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if not payload.get("results"):
    raise SystemExit("memory search returned no results after chat smoke")
PY
fi

echo "smoke checks passed"
