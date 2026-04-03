#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/env/lms_geotiff_template.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

CMD=(
  python3 -m geodata_auto_ingest.sources.lms_geotiff_template
  --src-file "$SRC_FILE"
  --iso-timestamp "$ISO_TIMESTAMP"
  --ingest-stem "$INGEST_STEM"
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

if [[ -n "${BOUNDARY:-}" ]]; then
  CMD+=(--boundary "$BOUNDARY")
fi

"${CMD[@]}"
