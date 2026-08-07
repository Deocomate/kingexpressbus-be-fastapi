"""Application settings loaded from environment."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "King Express Bus API"
    app_env: str = "local"
    app_debug: bool = True
    app_timezone: str = "Asia/Ho_Chi_Minh"

    # MySQL — split fields assembled into database_url
    db_connection: str = "mysql"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_database: str = "db_kingexpressbus"
    db_username: str = "root"
    db_password: str = ""

    jwt_secret: str = "change-me-jwt-secret-min-32-chars-xx"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    success_url_signing_key: str = "change-me-success-signing-key"

    cookie_name: str = "keb_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    cors_origins: str = "*"

    upload_root: str = "./uploads"


    frontend_base_url: str = "http://localhost:3000"
    success_path_template: str = "/dat-ve/thanh-cong/{booking}"

    sepay_environment: str = "sandbox"
    sepay_merchant_id: str = ""
    sepay_secret_key: str = ""
    sepay_checkout_url: str = "https://pay-sandbox.sepay.vn/v1/checkout/init"

    mail_host: str = "smtp.gmail.com"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""
    mail_use_tls: bool = True
    mail_from: str = "noreply@example.com"
    mail_from_name: str = "King Express Bus"
    admin_notify_email: str = "admin@example.com"
    mail_max_attempts: int = 3
    mail_queue_inline: bool = True

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL built from DB_* fields."""
        user = quote_plus(self.db_username)
        password = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database}"
            f"?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        parts = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return parts

    @property
    def cors_allows_all(self) -> bool:
        return "*" in self.cors_origin_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
