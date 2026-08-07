"""Upload staging scoped by authenticated admin user_id (not Laravel session)."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings

_TMP = "admin-tmp"


def _slug_filename(name: str) -> str:
    stem = Path(name).stem
    ext = Path(name).suffix.lstrip(".") or "bin"
    stem = re.sub(r"[^\w\-]+", "-", stem.lower()).strip("-") or "file"
    return f"{stem}.{ext}"


def _sign(secret: str, payload: dict) -> str:
    raw = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _verify(secret: str, token: str) -> dict:
    try:
        raw, sig = token.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid upload token") from exc
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid upload token signature")
    return json.loads(urlsafe_b64decode(raw.encode()))


def _user_key(user_id: int) -> str:
    return f"u{user_id}"


async def stage_file(
    settings: Settings,
    *,
    user_id: int,
    file: UploadFile,
) -> str:
    root = Path(settings.upload_root)
    file_uuid = str(uuid.uuid4())
    filename = _slug_filename(file.filename or "upload.bin")
    session = _user_key(user_id)
    dest_dir = root / _TMP / session / file_uuid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    content = await file.read()
    dest.write_bytes(content)
    return _sign(
        settings.jwt_secret,
        {"session": session, "uuid": file_uuid, "filename": filename},
    )


def revert_file(settings: Settings, *, user_id: int, token: str) -> None:
    payload = _verify(settings.jwt_secret, token)
    session = _user_key(user_id)
    if payload.get("session") != session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Token does not belong to this user")
    dest_dir = Path(settings.upload_root) / _TMP / session / payload["uuid"]
    if dest_dir.exists():
        for child in dest_dir.iterdir():
            child.unlink(missing_ok=True)
        dest_dir.rmdir()


def commit_file(
    settings: Settings,
    *,
    user_id: int,
    token: str,
    target_directory: str,
) -> str:
    payload = _verify(settings.jwt_secret, token)
    session = _user_key(user_id)
    if payload.get("session") != session:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Token session mismatch during commit")
    root = Path(settings.upload_root)
    src = root / _TMP / session / payload["uuid"] / payload["filename"]
    if not src.exists():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Staged file not found")
    target_directory = target_directory.strip("/")
    dest_dir = root / target_directory
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = payload["filename"]
    dest = dest_dir / dest_name
    if dest.exists():
        stem = Path(dest_name).stem
        ext = Path(dest_name).suffix
        dest = dest_dir / f"{stem}-{secrets.token_hex(3)}{ext}"
    dest.write_bytes(src.read_bytes())
    # cleanup
    for child in src.parent.iterdir():
        child.unlink(missing_ok=True)
    src.parent.rmdir()
    return f"{target_directory}/{dest.name}".replace("\\", "/")
