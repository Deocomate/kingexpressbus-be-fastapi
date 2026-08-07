"""Admin schemas: uploads, dashboard stats."""

from typing import Any

from pydantic import BaseModel


class UploadStageOut(BaseModel):
    token: str


class UploadCommitRequest(BaseModel):
    token: str
    target_directory: str = "uploads"


class UploadCommitOut(BaseModel):
    path: str


class UploadRevertRequest(BaseModel):
    token: str


class DashboardStatsOut(BaseModel):
    total_today: int
    pending_total: int
    revenue_today: int
    total_revenue: int
    status_counts: dict[str, int]
    monthly_revenue: list[dict[str, Any]]
