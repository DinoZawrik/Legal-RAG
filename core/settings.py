#!/usr/bin/env python3
"""Core settings module extracted from infrastructure suite."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # Optional dependency for loading .env files
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - optional helper
    pass

try:
    from pydantic import Field, SecretStr, validator, PostgresDsn, RedisDsn  # type: ignore
    try:
        from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore
    except ImportError:  # pragma: no cover - fallback for older pydantic
        from pydantic import BaseSettings  # type: ignore

        class SettingsConfigDict:  # type: ignore
            def __init__(self, **_kwargs: Any) -> None:
                pass
except ImportError as exc:  # pragma: no cover - graceful degradation
    logging.warning(f"Settings dependencies not available: {exc}")

    class BaseSettings:  # type: ignore
        def __init__(self, **_kwargs: Any) -> None:
            pass

    class SettingsConfigDict:  # type: ignore
        def __init__(self, **_kwargs: Any) -> None:
            pass

    def Field(default: Any = None, **_kwargs: Any) -> Any:  # type: ignore
        return default

    def validator(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func):
            return func

        return decorator

    class SecretStr(str):  # type: ignore
        def get_secret_value(self) -> str:
            return str(self)

    PostgresDsn = RedisDsn = str  # type: ignore

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Pydantic-based configuration loader."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    PROJECT_NAME: str = "LegalRAG"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    LOG_DIR: Path = BASE_DIR / "logs"
    UPLOADS_DIR: Path = BASE_DIR / "uploads"

    GOOGLE_API_KEY: Optional[SecretStr] = Field(None, env="GOOGLE_API_KEY")
    GEMINI_API_KEY: Optional[SecretStr] = Field(None, env="GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[SecretStr] = Field(None, env="OPENAI_API_KEY")

    POSTGRES_HOST: str = Field("localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(5432, env="POSTGRES_PORT")
    POSTGRES_DB: str = Field("legal_rag_db", env="POSTGRES_DB")
    POSTGRES_USER: str = Field("legal_rag_user", env="POSTGRES_USER")
    POSTGRES_PASSWORD: Optional[SecretStr] = Field(None, env="POSTGRES_PASSWORD")
    DATABASE_URL: Optional[PostgresDsn] = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v

        postgres_password = values.get("POSTGRES_PASSWORD")
        password_value: Optional[str] = None
        if postgres_password:
            password_value = (
                postgres_password.get_secret_value()
                if hasattr(postgres_password, "get_secret_value")
                else str(postgres_password)
            )

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.get("POSTGRES_USER"),
            password=password_value,
            host=values.get("POSTGRES_HOST"),
            port=values.get("POSTGRES_PORT"),
            path=values.get("POSTGRES_DB"),
        )

    REDIS_HOST: str = Field("localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_DB: int = Field(0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[SecretStr] = Field(None, env="REDIS_PASSWORD")
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v

        redis_password = values.get("REDIS_PASSWORD")
        password_value: Optional[str] = None
        if redis_password:
            password_value = (
                redis_password.get_secret_value()
                if hasattr(redis_password, "get_secret_value")
                else str(redis_password)
            )

        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=values.get("REDIS_PORT"),
            path=f"/{values.get('REDIS_DB')}",
            password=password_value,
        )

    CHROMA_HOST: str = Field("localhost", env="CHROMA_HOST")
    CHROMA_PORT: int = Field(8000, env="CHROMA_PORT")
    EMBEDDING_MODEL: str = Field("models/text-embedding-004", env="EMBEDDING_MODEL")
    DEFAULT_COLLECTION_NAME: str = Field("documents", env="DEFAULT_COLLECTION_NAME")

    DEBUG: bool = Field(False, env="DEBUG")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    MAX_FILE_SIZE_MB: int = Field(100, env="MAX_FILE_SIZE_MB")
    SUPPORTED_FILE_TYPES: List[str] = Field(
        default=[".pdf", ".txt", ".docx", ".xlsx"], env="SUPPORTED_FILE_TYPES"
    )

    CHUNK_SIZE: int = Field(1000, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(200, env="CHUNK_OVERLAP")
    MAX_CONCURRENT_TASKS: int = Field(5, env="MAX_CONCURRENT_TASKS")

    USE_OPTIMAL_RAG: bool = Field(False, env="USE_OPTIMAL_RAG")
    RAG_CACHE_TTL: int = Field(300, env="RAG_CACHE_TTL")

    TELEGRAM_BOT_TOKEN: Optional[SecretStr] = Field(None, env="TELEGRAM_BOT_TOKEN")
    TELEGRAM_ADMIN_IDS: List[int] = Field(default=[], env="TELEGRAM_ADMIN_IDS")
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(None, env="TELEGRAM_WEBHOOK_URL")
    TELEGRAM_SECRET_TOKEN: Optional[SecretStr] = Field(None, env="TELEGRAM_SECRET_TOKEN")

    REGULATORY_DOCS_DIR: Path = Field(None, env="REGULATORY_DOCS_DIR")

    SUMMARY_MODEL_NAME: str = Field("gemini-2.5-flash", env="SUMMARY_MODEL_NAME")
    QA_MODEL_NAME: str = Field("gemini-2.5-flash", env="QA_MODEL_NAME")
    EXTRACTOR_MODEL_NAME: str = Field("gemini-2.5-flash", env="EXTRACTOR_MODEL_NAME")
    AGENT_MODEL_NAME: str = Field("gemini-2.5-flash", env="AGENT_MODEL_NAME")

    google_api_key_agent: Optional[SecretStr] = Field(None, env="GOOGLE_API_KEY")
    redis_host: str = Field("localhost", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_db: int = Field(0, env="REDIS_DB")
    retriever_k: int = Field(5, env="RETRIEVER_K")

    @validator("REGULATORY_DOCS_DIR", "LOG_DIR", "UPLOADS_DIR", pre=True)
    def ensure_path(cls, v: Any) -> Path:
        path = Path(v)
        if any(part in str(path).lower() for part in ("regulatory_docs", "logs", "uploads")):
            path.mkdir(parents=True, exist_ok=True)
        return path

    @validator("SUPPORTED_FILE_TYPES", pre=True)
    def split_supported_file_types(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @validator("TELEGRAM_ADMIN_IDS", pre=True)
    def split_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return [int(item.strip()) for item in v.split(",") if item.strip()]
        return v


class SimpleSettings:
    """Lightweight settings loader without pydantic dependency."""

    def __init__(self) -> None:
        self.BASE_DIR = Path(__file__).resolve().parent.parent

        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
        self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
        self.POSTGRES_DB = os.getenv("POSTGRES_DB", "legal_rag_db")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER", "legal_rag_user")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me_in_env")

        self.REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_DB = int(os.getenv("REDIS_DB", "0"))

        self.CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
        self.CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
        self.CHROMA_USE_HTTP = os.getenv("CHROMA_USE_HTTP", "true").lower() == "true"
        self.DEFAULT_COLLECTION_NAME = os.getenv("DEFAULT_COLLECTION_NAME", "documents")

        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "models/text-embedding-004")
        self.AGENT_MODEL_NAME = os.getenv("AGENT_MODEL_NAME", "gemini-1.5-flash")
        self.EXTRACTION_MODEL_NAME = os.getenv("EXTRACTION_MODEL_NAME", "gemini-1.5-flash")
        self.SUMMARY_MODEL_NAME = os.getenv("SUMMARY_MODEL_NAME", "gemini-1.5-flash")
        self.QA_MODEL_NAME = os.getenv("QA_MODEL_NAME", "gemini-1.5-flash")

        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
        self.CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))

        self.USE_OPTIMAL_RAG = os.getenv("USE_OPTIMAL_RAG", "false").lower() == "true"
        self.RAG_CACHE_TTL = int(os.getenv("RAG_CACHE_TTL", "300"))
        self.RETRIEVER_K = int(os.getenv("RETRIEVER_K", "5"))

        self.TELEGRAM_ADMIN_IDS = self._parse_int_list(os.getenv("TELEGRAM_ADMIN_IDS", ""))
        self.REGULATORY_DOCS_DIR = self._ensure_dir(os.getenv("REGULATORY_DOCS_DIR", self.BASE_DIR / "regulatory_docs"))

        self.LOG_DIR = self._ensure_dir(os.getenv("LOG_DIR", self.BASE_DIR / "logs"))
        self.UPLOADS_DIR = self._ensure_dir(os.getenv("UPLOADS_DIR", self.BASE_DIR / "uploads"))
        self.SUPPORTED_FILE_TYPES = self._parse_str_list(os.getenv("SUPPORTED_FILE_TYPES", ".pdf,.txt,.docx,.xlsx"))

        self.NEO4J_HOST = os.getenv("NEO4J_HOST", "localhost")
        self.NEO4J_PORT = int(os.getenv("NEO4J_PORT", "7687"))
        self.NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "change_me_in_env")

    @staticmethod
    def _parse_int_list(value: str) -> List[int]:
        if not value:
            return []

        # Handle JSON-like format [1,2,3] or simple CSV format 1,2,3
        value = value.strip()
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1]  # Remove brackets

        return [int(item.strip()) for item in value.split(",") if item.strip()]

    @staticmethod
    def _parse_str_list(value: str) -> List[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    def _ensure_dir(self, path_like: Any) -> Path:
        path = Path(path_like)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def DATABASE_URL(self) -> str:
        password = self.POSTGRES_PASSWORD or ""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        password = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


_SETTINGS_INSTANCE: SimpleSettings = SimpleSettings()


def get_settings() -> SimpleSettings:
    """Return the global settings singleton."""
    return _SETTINGS_INSTANCE


def reload_settings() -> SimpleSettings:
    """Recreate the settings singleton (used in tests)."""
    global _SETTINGS_INSTANCE
    _SETTINGS_INSTANCE = SimpleSettings()
    return _SETTINGS_INSTANCE


# Backwards compatibility alias expected by legacy imports
SETTINGS = get_settings()

__all__ = ["Settings", "SimpleSettings", "SETTINGS", "get_settings", "reload_settings"]
