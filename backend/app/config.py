from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_title: str = Field(default="Cycle-Safe Referral Engine", alias="API_TITLE")
    database_url: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5432/referral_db", alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS")
    max_claims_per_minute: int = Field(default=5, alias="MAX_CLAIMS_PER_MINUTE")
    reward_max_depth: int = Field(default=3, alias="REWARD_MAX_DEPTH")
    default_reward_amounts: str = Field(default="10,5,2", alias="DEFAULT_REWARD_AMOUNTS")
    debug: bool = Field(default=True, alias="DEBUG")
    # Auth
    jwt_secret_key: str = Field(default="change-me-in-production-at-least-32-chars-long", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    admin_bootstrap_email: str = Field(default="admin@example.com", alias="ADMIN_BOOTSTRAP_EMAIL")
    admin_bootstrap_password: str = Field(default="admin123", alias="ADMIN_BOOTSTRAP_PASSWORD")

    @property
    def reward_amount_list(self) -> list[float]:
        return [float(item.strip()) for item in self.default_reward_amounts.split(",") if item.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
