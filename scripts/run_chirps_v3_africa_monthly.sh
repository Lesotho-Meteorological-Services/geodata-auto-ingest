#!/usr/bin/env bash
set -euo pipefail

LOCKFILE=/tmp/geodata_auto_ingest_chirps_v3_monthly.lock
exec 9>"$LOCKFILE"
flock -n 9 || { echo "Another CHIRPS v3 monthly ingest run is already in progress."; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/env/chirps_v3_africa_monthly.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

source "$ENV_FILE"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

python3 -m geodata_auto_ingest.sources.chirps_v3_africa_monthly \
  --latest \
  --base-url "$BASE_URL" \
  --version-prefix "$VERSION_PREFIX" \
  --boundary "$BOUNDARY" \
  --work-dir "$WORK_DIR" \
  --ingest-dir "$INGEST_DIR" \
  --layer-dir-name "$LAYER_DIR_NAME" \
  --container "$CONTAINER" \
  --manage-py "$GEOMANAGER_MANAGE_PY" \
  --log-dir "$LOG_DIR" \
  --log-file "$LOG_FILE" \
  --log-max-bytes "$LOG_MAX_BYTES" \
  --log-backup-count "$LOG_BACKUP_COUNT"
