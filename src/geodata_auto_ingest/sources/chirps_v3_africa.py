#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from geodata_auto_ingest.common.chirps import (
    ChirpsNaming,
    dekad_iso_timestamp,
    download_file,
    gunzip_file,
)
from geodata_auto_ingest.common.ingest import clip_geotiff, run_geomanager_ingest, stage_for_ingest
from geodata_auto_ingest.common.logging_utils import configure_logging
from geodata_auto_ingest.common.shell import ensure_dir


DEFAULT_BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/dekads/africa/tifs/"
DEFAULT_VERSION_PREFIX = "chirps-v3.0"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download, clip, stage, and auto-ingest a CHIRPS v3 Africa dekadal GeoTIFF into GeoManager/Climweb."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--latest", action="store_true", help="Process the latest dekad visible in the remote directory listing")
    mode.add_argument("--base-name", help=f"Explicit CHIRPS base name, e.g. {DEFAULT_VERSION_PREFIX}.2026.02.3")
    mode.add_argument("--ymd", nargs=3, metavar=("YEAR", "MONTH", "DEKAD"), help="Explicit year, month, dekad. Example: --ymd 2026 02 3")

    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Remote CHIRPS directory URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--version-prefix", default=DEFAULT_VERSION_PREFIX, help=f"Filename prefix. Default: {DEFAULT_VERSION_PREFIX}")
    parser.add_argument("--boundary", required=True, type=Path, help="Boundary file to use with gdalwarp -cutline")
    parser.add_argument("--work-dir", required=True, type=Path, help="Working directory used for raw and clipped files")
    parser.add_argument("--ingest-dir", required=True, type=Path, help="Host path of the GeoManager auto-ingest directory for this layer")
    parser.add_argument("--layer-dir-name", required=True, help="GeoManager layer directory name passed to process_geomanager_layer_directory")
    parser.add_argument("--container", default="climweb", help="Docker container name for the Climweb app. Default: climweb")
    parser.add_argument("--country-suffix", default="LSO", help="Suffix inserted into clipped filenames. Default: LSO")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing local files and re-run GeoManager ingest with --overwrite")
    parser.add_argument("--skip-ingest", action="store_true", help="Do everything except the docker exec ingest step")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-dir", type=Path, required=True, help="Directory for rotating logs")
    parser.add_argument("--log-file", default="chirps_v3_africa.log", help="Rotating log filename")
    parser.add_argument("--log-max-bytes", type=int, default=5_242_880, help="Max bytes per log file before rotation")
    parser.add_argument("--log-backup-count", type=int, default=5, help="Number of rotated log files to keep")
    return parser


def resolve_base_name(args: argparse.Namespace, naming: ChirpsNaming) -> str:
    if args.latest:
        return naming.latest_remote_file(args.base_url)
    if args.base_name:
        return args.base_name
    year, month, dekad = map(int, args.ymd)
    return naming.build_base_name(year, month, dekad)


def main() -> int:
    args = build_arg_parser().parse_args()
    logger = configure_logging(
        logger_name="geodata_auto_ingest.chirps_v3_africa",
        log_dir=args.log_dir,
        log_file=args.log_file,
        max_bytes=args.log_max_bytes,
        backup_count=args.log_backup_count,
        verbose=args.verbose,
    )

    if not args.boundary.exists():
        raise SystemExit(f"Boundary file not found: {args.boundary}")

    naming = ChirpsNaming(args.version_prefix)
    base_name = resolve_base_name(args, naming)
    year, month, dekad = naming.parse_base_name(base_name)
    iso_timestamp = dekad_iso_timestamp(year, month, dekad)

    raw_dir = args.work_dir / "raw"
    clipped_dir = args.work_dir / "clipped"
    ensure_dir(raw_dir)
    ensure_dir(clipped_dir)
    ensure_dir(args.ingest_dir)

    compressed_name = f"{base_name}.tif.gz"
    tif_name = f"{base_name}.tif"
    clipped_name = f"{base_name}-{args.country_suffix}.tif"
    ingest_name = f"{base_name}-{args.country_suffix}_{iso_timestamp}.tif"

    compressed_path = raw_dir / compressed_name
    tif_path = raw_dir / tif_name
    clipped_path = clipped_dir / clipped_name

    download_file(args.base_url.rstrip("/") + "/" + compressed_name, compressed_path, args.overwrite)
    gunzip_file(compressed_path, tif_path, args.overwrite)
    clip_geotiff(tif_path, args.boundary, clipped_path, args.overwrite)
    ingest_path = stage_for_ingest(clipped_path, args.ingest_dir, ingest_name, args.overwrite)

    logger.info("Prepared CHIRPS dekad %s with ingest timestamp %s", base_name, iso_timestamp)
    logger.info("Ingest file ready at %s", ingest_path)

    if not args.skip_ingest:
        run_geomanager_ingest(
            container=args.container,
            layer_dir_name=args.layer_dir_name,
            overwrite=args.overwrite,
            clip_to_boundary=False,
        )
        logger.info("GeoManager ingest complete for directory %s", args.layer_dir_name)
    else:
        logger.info("--skip-ingest set, not running GeoManager ingest command")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
