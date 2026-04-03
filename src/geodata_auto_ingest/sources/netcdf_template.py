#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from geodata_auto_ingest.common.ingest import (
    copy_or_download,
    netcdf_ingest_name,
    run_geomanager_ingest,
    stage_for_ingest,
    try_validate_netcdf_variable,
    validate_extension,
)
from geodata_auto_ingest.common.logging_utils import configure_logging
from geodata_auto_ingest.common.shell import ensure_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage and auto-ingest a NetCDF file into GeoManager/Climweb."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--src-file", type=Path, help="Local NetCDF file to stage")
    source.add_argument("--url", help="Remote NetCDF URL to download before staging")

    parser.add_argument("--staged-name", required=True, help="Base file name to use before the .nc extension inside the ingest directory")
    parser.add_argument("--work-dir", required=True, type=Path, help="Working directory used for downloads or local staging")
    parser.add_argument("--ingest-dir", required=True, type=Path, help="Host path of the GeoManager auto-ingest directory for this layer")
    parser.add_argument("--layer-dir-name", required=True, help="GeoManager layer directory name passed to process_geomanager_layer_directory")
    parser.add_argument("--container", default="climweb", help="Docker container name for the Climweb app. Default: climweb")
    parser.add_argument("--expected-variable", help="Optional local validation of the NetCDF variable name; should match the layer's NetCDF data variable in GeoManager")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing staged files and re-run GeoManager ingest with --overwrite")
    parser.add_argument("--clip-in-geomanager", action="store_true", help="Pass --clip to GeoManager so clipping is handled inside GeoManager against configured admin boundaries")
    parser.add_argument("--skip-ingest", action="store_true", help="Do everything except the docker exec ingest step")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-dir", type=Path, required=True, help="Directory for rotating logs")
    parser.add_argument("--log-file", default="netcdf_template.log", help="Rotating log filename")
    parser.add_argument("--log-max-bytes", type=int, default=5_242_880, help="Max bytes per log file before rotation")
    parser.add_argument("--log-backup-count", type=int, default=5, help="Number of rotated log files to keep")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    logger = configure_logging(
        logger_name="geodata_auto_ingest.netcdf_template",
        log_dir=args.log_dir,
        log_file=args.log_file,
        max_bytes=args.log_max_bytes,
        backup_count=args.log_backup_count,
        verbose=args.verbose,
    )

    ensure_dir(args.work_dir)
    ensure_dir(args.ingest_dir)

    stage_input_path = args.work_dir / ("downloaded.nc" if args.url else args.src_file.name)
    copied_path = copy_or_download(args.src_file, args.url, stage_input_path, args.overwrite)
    validate_extension(copied_path, (".nc",))
    try_validate_netcdf_variable(copied_path, args.expected_variable, logger)

    ingest_name = netcdf_ingest_name(args.staged_name, ".nc")
    ingest_path = stage_for_ingest(copied_path, args.ingest_dir, ingest_name, args.overwrite)
    logger.info("NetCDF ready for GeoManager ingest: %s", ingest_path)

    if not args.skip_ingest:
        run_geomanager_ingest(
            container=args.container,
            layer_dir_name=args.layer_dir_name,
            overwrite=args.overwrite,
            clip_to_boundary=args.clip_in_geomanager,
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
