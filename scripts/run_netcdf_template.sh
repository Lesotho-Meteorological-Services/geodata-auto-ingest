#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/env/netcdf_template.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

CMD=(
  python3 -m geodata_auto_ingest.sources.netcdf_template
  --staged-name "$STAGED_NAME"
  --work-dir "$WORK_DIR"
  --ingest-dir "$INGEST_DIR"
  --layer-dir-name "$LAYER_DIR_NAME"
  --container "$CONTAINER"
  --log-dir "$LOG_DIR"
  --log-file "$LOG_FILE"
  --log-max-bytes "$LOG_MAX_BYTES"
  --log-backup-count "$LOG_BACKUP_COUNT"
  --overwrite
)

if [[ -n "${SRC_FILE:-}" ]]; then
  CMD+=(--src-file "$SRC_FILE")
fi

if [[ -n "${URL:-}" ]]; then
  CMD+=(--url "$URL")
fi

if [[ -n "${EXPECTED_VARIABLE:-}" ]]; then
  CMD+=(--expected-variable "$EXPECTED_VARIABLE")
fi

if [[ "${CLIP_IN_GEOMANAGER:-false}" == "true" ]]; then
  CMD+=(--clip-in-geomanager)
fi

"${CMD[@]}"
