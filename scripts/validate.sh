#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${VERCEL_URL:-}" ]]; then
  echo "Set VERCEL_URL, e.g. VERCEL_URL=https://your-project.vercel.app bash scripts/validate.sh" >&2
  exit 1
fi

space_url="${SPACE_URL:-}"
space_token="${SPACE_TOKEN:-}"

echo "[1/5] Local file checks"
test -f supabase/init.sql && test -f anythingllm/agent_tools.json && echo "OK: required config files present"

echo "[2/5] Validate tool JSON"
python -m json.tool anythingllm/agent_tools.json >/dev/null && echo "OK: agent_tools.json is valid JSON"

echo "[3/5] Hit mood endpoint"
curl -fsS "$VERCEL_URL/api/mood" \
  -H 'Content-Type: application/json' \
  -d '{"text":"I feel calm and hopeful today."}' | jq .

echo "[4/5] Hit music endpoint"
curl -fsS "$VERCEL_URL/api/music_trigger" \
  -H 'Content-Type: application/json' \
  -d '{"mood":"neutral"}' | jq .

echo "[5/5] Optional AnythingLLM system check"
if [[ -n "$space_url" && -n "$space_token" ]]; then
  bash scripts/fetch_system_fields.sh "$space_url" "$space_token"
else
  echo "SKIP: set SPACE_URL and SPACE_TOKEN to run /api/v1/system verification"
fi

echo "Validation flow completed."
