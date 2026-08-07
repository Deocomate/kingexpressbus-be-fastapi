"""Admin staged-upload lifecycle (stage / revert / commit)."""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from app.api.v1.admin.deps import AdminUser, SameOrigin
from app.core.deps import AppSettings
from app.core.rate_limit import client_ip, rate_limiter
from app.schemas.admin_common import MessageOut
from app.schemas.admin_meta import (
    UploadCommitOut,
    UploadCommitRequest,
    UploadRevertRequest,
    UploadStageOut,
)
from app.services import uploads as upload_service

router = APIRouter(prefix="/admin", tags=["admin-meta"])


@router.post("/uploads", response_model=UploadStageOut)
async def stage_upload(
    request: Request,
    admin: AdminUser,
    _: SameOrigin,
    settings: AppSettings,
    file: UploadFile = File(...),
) -> UploadStageOut:
    rate_limiter.hit(f"admin:uploads:ip:{client_ip(request)}", limit=20)
    token = await upload_service.stage_file(settings, user_id=admin.id, file=file)
    return UploadStageOut(token=token)


@router.delete("/uploads", response_model=MessageOut)
async def revert_upload(
    body: UploadRevertRequest,
    admin: AdminUser,
    _: SameOrigin,
    settings: AppSettings,
) -> MessageOut:
    upload_service.revert_file(settings, user_id=admin.id, token=body.token)
    return MessageOut(message="Reverted")


@router.post("/uploads/commit", response_model=UploadCommitOut)
async def commit_upload(
    body: UploadCommitRequest,
    admin: AdminUser,
    _: SameOrigin,
    settings: AppSettings,
) -> UploadCommitOut:
    path = upload_service.commit_file(
        settings,
        user_id=admin.id,
        token=body.token,
        target_directory=body.target_directory,
    )
    return UploadCommitOut(path=path)
