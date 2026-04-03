from __future__ import annotations

import gzip
import html
import logging
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

LOG = logging.getLogger(__name__)


class ChirpsNaming:
    def __init__(self, version_prefix: str) -> None:
        self.version_prefix = version_prefix
        self.file_re = re.compile(
            rf"{re.escape(version_prefix)}\.(\d{{4}})\.(\d{{2}})\.([123])\.tif(?:\.gz)?"
        )
        self.base_re = re.compile(
            rf"{re.escape(version_prefix)}\.(\d{{4}})\.(\d{{2}})\.([123])"
        )

    def build_base_name(self, year: int, month: int, dekad: int) -> str:
        if dekad not in (1, 2, 3):
            raise ValueError("Dekad must be 1, 2, or 3")
        return f"{self.version_prefix}.{year:04d}.{month:02d}.{dekad}"

    def parse_base_name(self, base_name: str) -> tuple[int, int, int]:
        match = self.base_re.fullmatch(base_name)
        if not match:
            raise ValueError(
                f"Base name must look like {self.version_prefix}.YYYY.MM.D, "
                f"for example {self.version_prefix}.2026.02.3"
            )
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    def latest_remote_file(self, base_url: str) -> str:
        with urllib.request.urlopen(base_url) as response:
            listing = response.read().decode("utf-8", errors="replace")
        matches = sorted(set(self.file_re.findall(html.unescape(listing))))
        if not matches:
            raise RuntimeError(f"No CHIRPS dekadal files found at {base_url}")
        year, month, dekad = matches[-1]
        return self.build_base_name(int(year), int(month), int(dekad))


def dekad_iso_timestamp(year: int, month: int, dekad: int) -> str:
    day = {1: 1, 2: 11, 3: 21}[dekad]
    return f"{year:04d}-{month:02d}-{day:02d}T00:00:00.000Z"


def download_file(url: str, dest: Path, overwrite: bool) -> None:
    if dest.exists() and not overwrite:
        LOG.info("Download exists, skipping: %s", dest)
        return
    LOG.info("Downloading %s -> %s", url, dest)
    with urllib.request.urlopen(url) as response, dest.open("wb") as output_file:
        shutil.copyfileobj(response, output_file)


def gunzip_file(src: Path, dest: Path, overwrite: bool) -> None:
    if dest.exists() and not overwrite:
        LOG.info("Uncompressed file exists, skipping: %s", dest)
        return
    LOG.info("Uncompressing %s -> %s", src, dest)
    with gzip.open(src, "rb") as gz_stream, dest.open("wb") as output_file:
        shutil.copyfileobj(gz_stream, output_file)


def remote_file_name(base_url: str, base_name: str) -> str:
    candidates = [f"{base_name}.tif.gz", f"{base_name}.tif"]
    for candidate in candidates:
        url = base_url.rstrip('/') + '/' + candidate
        try:
            request = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(request):
                return candidate
        except Exception:
            continue
    raise RuntimeError(f'Neither {base_name}.tif.gz nor {base_name}.tif exists at {base_url}')


def prepare_raster_from_remote(downloaded_path: Path, tif_dest: Path, overwrite: bool) -> None:
    if downloaded_path.suffix == '.gz':
        gunzip_file(downloaded_path, tif_dest, overwrite)
    else:
        if tif_dest.exists() and not overwrite:
            LOG.info('Prepared tif exists, skipping: %s', tif_dest)
            return
        LOG.info('Copying %s -> %s', downloaded_path, tif_dest)
        shutil.copy2(downloaded_path, tif_dest)
