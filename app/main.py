"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.presentation.api.v1 import api_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        # "*" → Starlette reflects request Origin when credentials=True
        allow_origins=["*"] if settings.cors_allows_all else settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
