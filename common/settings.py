import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "paytm-style")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change")
    jwt_ttl_seconds: int = int(os.getenv("JWT_TTL_SECONDS", "3600"))
    internal_jwt_ttl_seconds: int = int(os.getenv("INTERNAL_JWT_TTL_SECONDS", "300"))

    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "root")
    mysql_host: str = os.getenv("MYSQL_HOST", "mysql")
    mysql_db: str = os.getenv("MYSQL_DB", "ledger")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))

    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    cassandra_host: str = os.getenv("CASSANDRA_HOST", "cassandra")
    cassandra_keyspace: str = os.getenv("CASSANDRA_KEYSPACE", "paytm_style")

settings = Settings()
