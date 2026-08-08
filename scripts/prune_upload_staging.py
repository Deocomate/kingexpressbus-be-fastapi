"""CLI GC for stale admin upload staging directories.

Staged uploads live at `{upload_root}/admin-tmp/{session}/{uuid}/{filename}`
(see app/infrastructure/storage uploads stage_file) and are only meant to survive until
an admin commits or reverts them. Anything left behind past the cutoff
(crashed tab, abandoned form) is swept here.

Usage:
    python -m scripts.prune_upload_staging [--hours 24]

Cron (daily):
    0 0 * * * cd /path/to/kingexpressbus-backend-python && \
        .venv/bin/python -m scripts.prune_upload_staging >> /var/log/kingexpressbus/prune-uploads.log 2>&1
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from app.core.config import get_settings

_TMP_DIR_NAME = "admin-tmp"


def prune_upload_staging(upload_root: Path, *, hours: float) -> tuple[int, int]:
    """Delete `admin-tmp/{session}/{uuid}` dirs whose mtime is older than `hours`.

    Returns (deleted, kept) directory counts. Empty session directories left
    behind after their uuid children are pruned are removed too.
    """
    admin_tmp = upload_root / _TMP_DIR_NAME
    if not admin_tmp.is_dir():
        return (0, 0)

    cutoff = time.time() - hours * 3600
    deleted = 0
    kept = 0

    for session_dir in sorted(p for p in admin_tmp.iterdir() if p.is_dir()):
        for uuid_dir in sorted(p for p in session_dir.iterdir() if p.is_dir()):
            if uuid_dir.stat().st_mtime < cutoff:
                shutil.rmtree(uuid_dir, ignore_errors=True)
                deleted += 1
            else:
                kept += 1

        # Remove the session directory once it has no staged uploads left.
        if session_dir.is_dir() and not any(session_dir.iterdir()):
            session_dir.rmdir()

    return (deleted, kept)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--hours",
        type=float,
        default=24,
        help="Delete staged upload directories older than this many hours (default: 24).",
    )
    args = parser.parse_args()

    settings = get_settings()
    upload_root = Path(settings.upload_root)
    if not upload_root.is_dir():
        print(f"Upload root {upload_root} does not exist — nothing to prune.")
        return 0

    deleted, kept = prune_upload_staging(upload_root, hours=args.hours)
    if deleted == 0 and kept == 0:
        print(f"{_TMP_DIR_NAME} directory does not exist — nothing to prune.")
        return 0

    unit = "directory" if deleted == 1 else "directories"
    print(f"Pruned {deleted} stale upload {unit}; kept {kept}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
