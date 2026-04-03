#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from geodata_auto_ingest.common.ingest import (
    clip_geotiff,
    geotiff_ingest_name,
    run_geomanager_ingest,
    stage_for_ingest,
    validate_extension,
)
from geodata_auto_ingest.common.logging_utils import configure_logging
from geodata_auto_ingest.common.shell import ensure_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage and auto-ingest a local GeoTIFF (for example from LMS) into GeoManager/Climweb."
    )
    parser.add_argument("--src-file", required=True, type=Path, help="Source GeoTIFF file")
    parser.add_argument("--iso-timestamp", required=True, help="ISO UTC timestamp suffix required by GeoManager, e.g. 2026-04-01T00:00:00.000Z")
    parser.add_argument("--ingest-stem", required=True, help="Base ingest file name without the timestamp suffix or extension")
    parser.add_argument("--work-dir", required=True, type=Path, help="Working directory used for optional clipping output")
    parser.add_argument("--ingest-dir", required=True, type=Path, help="Host path of the GeoManager auto-ingest directory for this layer")
    parser.add_argument("--layer-dir-name", required=True, help="GeoManager layer directory name passed to process_geomanager_layer_directory")
    parser.add_argument("--container", default="climweb", help="Docker container name for the Climweb app. Default: climweb")
    parser.add_argument("--boundary", type=Path, help="Optional boundary file for clipping before ingest")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing staged files and re-run GeoManager ingest with --overwrite")
    parser.add_argument("--skip-ingest", action="store_true", help="Do everything except the docker exec ingest step")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-dir", type=Path, required=True, help="Directory for rotating logs")
    parser.add_argument("--log-file", default="lms_geotiff_template.log", help="Rotating log filename")
    parser.add_argument("--log-max-bytes", type=int, default=5_242_880, help="Max bytes per log file before rotation")
    parser.add_argument("--log-backup-count", type=int, default=5, help="Number of rotated log files to keep")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    logger = configure_logging(
        logger_name="geodata_auto_ingest.lms_geotiff_template",
        log_dir=args.log_dir,
        log_file=args.log_file,
        max_bytes=args.log_max_bytes,
        backup_count=args.log_backup_count,
        verbose=args.verbose,
    )

    validate_extension(args.src_file, (".tif", ".tiff"))
    ensure_dir(args.work_dir)
    ensure_dir(args.ingest_dir)

    if args.boundary:
        if not args.boundary.exists():
            raise SystemExit(f"Boundary file not found: {args.boundary}")
        clipped_path = args.work_dir / f"{args.src_file.stem}-clipped.tif"
        clip_geotiff(args.src_file, args.boundary, clipped_path, args.overwrite)
        stage_source = clipped_path
    else:
        stage_source = args.src_file

    ingest_name = geotiff_ingest_name(args.ingest_stem, args.iso_timestamp, ".tif")
    ingest_path = stage_for_ingest(stage_source, args.ingest_dir, ingest_name, args.overwrite)
    logger.info("GeoTIFF ready for GeoManager ingest: %s", ingest_path)

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
