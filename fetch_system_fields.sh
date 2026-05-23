#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <base_url> <bearer_token>" >&2
  exit 1
fi

BASE_URL="${1%/}"
TOKEN="$2"

raw_json=$(curl -sS "$BASE_URL/api/v1/system" \
  -H "Authorization: Bearer $TOKEN")

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to parse response" >&2
  exit 1
fi

printf '%s\n' "$raw_json" | jq '{llmProvider, embeddingProvider, vectorDb, version}'
