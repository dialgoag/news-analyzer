#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Simple smoke suite for backend API endpoints that require JWT auth.
# Usage:
#   chmod +x scripts/run_api_smoke.sh
#   TOKEN="<jwt>" API_BASE="http://localhost:8000" scripts/run_api_smoke.sh
# -------------------------------------------------------------------

API_BASE=${API_BASE:-http://localhost:8000}
TOKEN=${TOKEN:-}

if [[ -z "${TOKEN}" ]]; then
  echo "Falta TOKEN. Ejecuta: TOKEN=\"<jwt>\" scripts/run_api_smoke.sh" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl no está instalado en este entorno." >&2
  exit 1
fi

auth_header=("Authorization: Bearer ${TOKEN}")

endpoints=(
  "GET /api/documents"
  "GET /api/workers/status"
  "GET /api/dashboard/summary"
  "GET /api/dashboard/analysis"
  "GET /api/admin/data-integrity"
)

for entry in "${endpoints[@]}"; do
  method=${entry%% *}
  path=${entry#* }
  url="${API_BASE}${path}"
  echo "------------------------------------------------------------"
  echo "${method} ${url}"
  curl -sS -X "${method}" -H "${auth_header[@]}" \
    -w "\nHTTP_STATUS:%{http_code}\n" \
    "${url}"
  echo
done
