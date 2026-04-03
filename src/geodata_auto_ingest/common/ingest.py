from __future__ import annotations

import logging
import shutil
import urllib.request
from pathlib import Path

from .shell import ensure_dir, run, which_required

LOG = logging.getLogger(__name__)


def clip_geotiff(src: Path, boundary: Path, dest: Path, overwrite: bool) -> None:
    if dest.exists() and not overwrite:
        LOG.info("Clipped raster exists, skipping: %s", dest)
        return
    which_required("gdalwarp")
    run(
        [
            "gdalwarp",
            "-overwrite",
            "-cutline",
            str(boundary),
            "-crop_to_cutline",
            "-multi",
            "-dstalpha",
            "-co",
            "TILED=YES",
            "-co",
            "COMPRESS=DEFLATE",
            str(src),
            str(dest),
        ]
    )


def copy_or_download(src_file: Path | None, url: str | None, dest: Path, overwrite: bool) -> Path:
    if src_file is None and url is None:
        raise ValueError("Either src_file or url must be provided")
    if src_file is not None and url is not None:
        raise ValueError("Provide either src_file or url, not both")

    if dest.exists() and not overwrite:
        LOG.info("Local staged input exists, skipping: %s", dest)
        return dest

    ensure_dir(dest.parent)

    if src_file is not None:
        if not src_file.exists():
            raise FileNotFoundError(f"Source file not found: {src_file}")
        LOG.info("Copying %s -> %s", src_file, dest)
        shutil.copy2(src_file, dest)
    else:
        LOG.info("Downloading %s -> %s", url, dest)
        with urllib.request.urlopen(url) as response, dest.open("wb") as output_file:
            shutil.copyfileobj(response, output_file)
    return dest


def stage_for_ingest(src: Path, ingest_dir: Path, ingest_name: str, overwrite: bool) -> Path:
    ensure_dir(ingest_dir)
    dest = ingest_dir / ingest_name
    if dest.exists():
        if overwrite:
            dest.unlink()
        else:
            LOG.info("Ingest file exists, skipping copy: %s", dest)
            return dest
    shutil.copy2(src, dest)
    LOG.info("Staged file for GeoManager ingest: %s", dest)
    return dest


def run_geomanager_ingest(
    *,
    container: str,
    layer_dir_name: str,
    overwrite: bool,
    clip_to_boundary: bool,
) -> None:
    which_required("docker")
    command = [
        "docker",
        "exec",
        "-i",
        container,
        "python",
        "/climweb/web/src/climweb/manage.py",
        "process_geomanager_layer_directory",
        layer_dir_name,
    ]
    if overwrite:
        command.append("--overwrite")
    if clip_to_boundary:
        command.append("--clip")
    run(command)


def geotiff_ingest_name(stem: str, iso_timestamp: str, suffix: str = ".tif") -> str:
    return f"{stem}_{iso_timestamp}{suffix}"


def netcdf_ingest_name(stem: str, suffix: str = ".nc") -> str:
    return f"{stem}{suffix}"


def validate_extension(path: Path, allowed: tuple[str, ...]) -> None:
    if path.suffix.lower() not in allowed:
        raise ValueError(f"Unsupported file extension for {path.name}. Allowed: {', '.join(allowed)}")


def try_validate_netcdf_variable(path: Path, variable_name: str | None, logger: logging.Logger) -> None:
    if not variable_name:
        logger.info("No expected NetCDF variable provided; skipping local validation")
        return

    try:
        import xarray as xr  # type: ignore
    except Exception:
        logger.warning(
            "xarray is not installed; skipping local NetCDF variable validation for '%s'. GeoManager will still validate during ingest.",
            variable_name,
        )
        return

    logger.info("Validating NetCDF variable '%s' in %s", variable_name, path)
    with xr.open_dataset(path) as ds:
        if variable_name not in ds.data_vars:
            raise ValueError(
                f"Expected NetCDF variable '{variable_name}' not found in {path.name}. Available variables: {list(ds.data_vars)}"
            )
        if "time" not in ds.coords and "time" not in ds.dims:
            logger.warning(
                "No obvious 'time' coordinate found in %s. GeoManager expects time values in NetCDF.",
                path.name,
            )
