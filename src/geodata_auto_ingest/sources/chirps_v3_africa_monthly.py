from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from geodata_auto_ingest.common.chirps import download_file, prepare_raster_from_remote
from geodata_auto_ingest.common.ingest import (
    clip_geotiff,
    stage_for_ingest,
    run_geomanager_ingest,
)
from geodata_auto_ingest.common.shell import ensure_dir
from geodata_auto_ingest.common.logging_utils import configure_logging
from urllib.request import urlopen
import re


def monthly_base_name(version_prefix: str, year: int, month: int) -> str:
    return f"{version_prefix}.{year:04d}.{month:02d}"


def monthly_iso_timestamp(year: int, month: int) -> str:
    dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def latest_remote_monthly_file(base_url: str, version_prefix: str) -> tuple[int, int, str]:
    with urlopen(base_url) as response:
        html = response.read().decode("utf-8", errors="ignore")

    pattern = rf"({re.escape(version_prefix)}\.(\d{{4}})\.(\d{{2}})\.tif(?:\.gz)?)"
    matches = re.findall(pattern, html)

    if not matches:
        raise RuntimeError(f"No monthly CHIRPS files found at {base_url}")

    candidates = []
    for full_name, year, month in matches:
        candidates.append((int(year), int(month), full_name))

    candidates.sort()
    year, month, full_name = candidates[-1]
    return year, month, full_name


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--ym", nargs=2, type=int, metavar=("YEAR", "MONTH"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--version-prefix", required=True)
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--ingest-dir", required=True)
    parser.add_argument("--layer-dir-name", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--manage-py", default=os.getenv("GEOMANAGER_MANAGE_PY", "/climweb/web/src/climweb/manage.py"))
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--log-max-bytes", type=int, required=True)
    parser.add_argument("--log-backup-count", type=int, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    configure_logging(
        logger_name="geodata_auto_ingest.sources.chirps_v3_africa_monthly",
        log_dir=args.log_dir,
        log_file=args.log_file,
        max_bytes=args.log_max_bytes,
        backup_count=args.log_backup_count,
    )

    work_dir = Path(args.work_dir)
    raw_dir = work_dir / "raw"
    clipped_dir = work_dir / "clipped"
    ensure_dir(raw_dir)
    ensure_dir(clipped_dir)
    ensure_dir(Path(args.ingest_dir))

    if args.latest:
        year, month, remote_name = latest_remote_monthly_file(args.base_url, args.version_prefix)
        base_name = monthly_base_name(args.version_prefix, year, month)
    else:
        if not args.ym:
            raise SystemExit("Use --latest or --ym YEAR MONTH")
        year, month = args.ym
        base_name = monthly_base_name(args.version_prefix, year, month)
        remote_name = f"{base_name}.tif"

    downloaded_path = raw_dir / remote_name
    tif_path = raw_dir / f"{base_name}.tif"
    clipped_name = f"{base_name}-LSO.tif"
    clipped_path = clipped_dir / clipped_name

    download_file(args.base_url.rstrip("/") + "/" + remote_name, downloaded_path, args.overwrite)
    prepare_raster_from_remote(downloaded_path, tif_path, args.overwrite)
    clip_geotiff(tif_path, Path(args.boundary), clipped_path, args.overwrite)

    iso_time = monthly_iso_timestamp(year, month)
    ingest_filename = f"{base_name}-LSO_{iso_time}.tif"
    ingest_path = Path(args.ingest_dir) / ingest_filename

    stage_for_ingest(clipped_path, Path(args.ingest_dir), ingest_filename, args.overwrite)

    if not args.skip_ingest:
        run_geomanager_ingest(
            container=args.container,
            layer_dir_name=args.layer_dir_name,
            overwrite=args.overwrite,
            manage_py=args.manage_py,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
