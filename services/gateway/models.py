"""Pydantic схемы, используемые в API Gateway."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Запрос на стандартный поиск."""

    query: str
    max_results: Optional[int] = 10
    use_cache: Optional[bool] = True
    config: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class UniversalLegalQueryRequest(BaseModel):
    """Запрос на универсальный правовой анализ."""

    query: str
    max_chunks: Optional[int] = 7
    strict_verification: Optional[bool] = True
    config: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class HybridSearchRequest(BaseModel):
    """Запрос на гибридный поиск (семантика + граф)."""

    query: str
    max_results: Optional[int] = 7
    graph_enabled: Optional[bool] = True
    graph_depth: Optional[int] = 2
    config: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class ServiceRequest(BaseModel):
    """Унифицированный прокси‑запрос к микросервисам."""

    service: str
    action: str
    data: Dict[str, Any]
    request_id: Optional[str] = None


class AdminLoginRequest(BaseModel):
    """Запрос на админ‑аутентификацию."""

    username: str
    password: str


class AdminFileUpload(BaseModel):
    """Параметры загрузки файла через админ‑панель."""

    category: str = "general"
    auto_process: bool = True
    skip_duplicates: bool = True
