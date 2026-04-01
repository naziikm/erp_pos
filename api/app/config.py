from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MySQL Database
    MYSQL_URL: str

    # ERPNext Connection
    ERP_BASE_URL: str
    ERP_API_KEY: str
    ERP_API_SECRET: str

    # JWT Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # License
    LICENSE_HMAC_SECRET: str

    # Sync Intervals
    STOCK_SYNC_INTERVAL_MINUTES: int = 15
    INVOICE_SYNC_INTERVAL_SECONDS: int = 30
    ERP_SYNC_INTERVAL_MINUTES: int = 5

    # ERP Client
    ERP_REQUEST_TIMEOUT_SECONDS: int = 30
    MAX_INVOICE_PUSH_ATTEMPTS: int = 3

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
