from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    api_v1_prefix: str = "/api/v1"
    allowed_origins: str = "http://localhost:3000"

    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "skyflare"
    jwt_audience: str = "skyflare-api"
    access_token_ttl: int = 900
    refresh_token_ttl: int = 604800

    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"

    login_rate_max_attempts: int = 5
    login_rate_window_seconds: int = 300

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True

    email_backend: str | None = None
    email_allow_noop_ack: bool = False
    email_max_attempts: int = 5
    email_retry_base_delay: int = 2
    email_max_retry_delay: int = 300
    email_max_concurrency: int = 4
    email_batch_size: int = 100
    email_poll_interval: float = 5.0
    email_processing_timeout: int = 120

    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = ""
    kafka_security_protocol: str = "SASL_SSL"
    kafka_sasl_mechanism: str = "PLAIN"
    kafka_sasl_username: str = ""
    kafka_sasl_password: str = ""
    kafka_ssl_cafile: str | None = None
    kafka_consumer_group: str = "notification-workers"
    kafka_source: str = "flight-api"
    kafka_provision_topics: bool = True
    kafka_topic_partitions: int = 1
    kafka_topic_replication: int = 1
    kafka_publish_batch_size: int = 100
    kafka_publish_concurrency: int = 4
    kafka_poll_interval: float = 5.0
    kafka_processing_timeout: int = 120
    kafka_publish_max_attempts: int = 5
    kafka_publish_base_delay: int = 2
    kafka_publish_max_delay: int = 300
    kafka_max_attempts: int = 5
    kafka_retry_base_delay: int = 2
    kafka_max_retry_delay: int = 300

    @property
    def resolved_email_backend(self) -> str:
        if self.email_backend:
            return self.email_backend
        return "smtp" if self.smtp_host else "noop"

    @property
    def kafka_broker_configured(self) -> bool:
        return bool(self.kafka_bootstrap_servers)

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

    @property
    def refresh_cookie_path(self) -> str:
        return f"{self.api_v1_prefix}/auth"


@lru_cache
def get_settings() -> Settings:
    return Settings()
