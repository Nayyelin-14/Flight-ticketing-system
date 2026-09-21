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


@lru_cache
def get_settings() -> Settings:
    return Settings()
