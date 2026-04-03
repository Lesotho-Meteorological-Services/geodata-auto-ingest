from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

LOG = logging.getLogger(__name__)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def which_required(binary: str) -> None:
    if shutil.which(binary) is None:
        raise RuntimeError(f"Required executable not found in PATH: {binary}")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    LOG.info("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True)
