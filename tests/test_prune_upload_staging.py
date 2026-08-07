import os
import time
from pathlib import Path

from scripts.prune_upload_staging import prune_upload_staging


def _make_staged_upload(root: Path, session: str, file_uuid: str, *, age_hours: float = 0) -> Path:
    dest_dir = root / "admin-tmp" / session / file_uuid
    dest_dir.mkdir(parents=True)
    file_path = dest_dir / "file.jpg"
    file_path.write_bytes(b"fake-content")
    if age_hours:
        stale = time.time() - age_hours * 3600
        os.utime(dest_dir, (stale, stale))
    return dest_dir


def test_deletes_directories_older_than_threshold(tmp_path: Path) -> None:
    old_dir = _make_staged_upload(tmp_path, "old-session", "old-uuid", age_hours=25)

    deleted, kept = prune_upload_staging(tmp_path, hours=24)

    assert deleted == 1
    assert kept == 0
    assert not old_dir.exists()
    # empty session dir is cleaned up too
    assert not (tmp_path / "admin-tmp" / "old-session").exists()


def test_keeps_directories_newer_than_threshold(tmp_path: Path) -> None:
    fresh_dir = _make_staged_upload(tmp_path, "new-session", "new-uuid", age_hours=0)

    deleted, kept = prune_upload_staging(tmp_path, hours=24)

    assert deleted == 0
    assert kept == 1
    assert fresh_dir.exists()
    assert (fresh_dir / "file.jpg").exists()


def test_missing_admin_tmp_directory_is_a_noop(tmp_path: Path) -> None:
    deleted, kept = prune_upload_staging(tmp_path, hours=24)

    assert (deleted, kept) == (0, 0)


def test_mixed_ages_only_prunes_stale_ones(tmp_path: Path) -> None:
    stale_dir = _make_staged_upload(tmp_path, "mixed-session", "stale-uuid", age_hours=48)
    fresh_dir = _make_staged_upload(tmp_path, "mixed-session", "fresh-uuid", age_hours=1)

    deleted, kept = prune_upload_staging(tmp_path, hours=24)

    assert deleted == 1
    assert kept == 1
    assert not stale_dir.exists()
    assert fresh_dir.exists()
    # session dir survives because it still has the fresh upload
    assert (tmp_path / "admin-tmp" / "mixed-session").exists()
