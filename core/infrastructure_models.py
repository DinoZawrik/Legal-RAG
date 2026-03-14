#!/usr/bin/env python3
"""
Infrastructure Data Models
Модели данных для инфраструктуры системы.

Включает функциональность:
- DocumentType, ProcessingStatus: Перечисления для типов и статусов
- Pydantic модели: Модели для валидации данных LangGraph workflow
- Dataclass модели: Основные модели документов и чанков
- State модели: Состояния для LangGraph workflow

ВАЖНОЕ ТРЕБОВАНИЕ из complex_task.txt:
Система должна использовать ТОЛЬКО документы из БД, а НЕ собственные знания модели.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union, TypedDict

try:
    from pydantic import BaseModel, Field
except ImportError as exc: # pragma: no cover - minimal fallback
    import logging
    logging.warning(f"Pydantic unavailable for infrastructure data models: {exc}")

    class BaseModel: # type: ignore
        def __init__(self, **_kwargs: Any) -> None:
            pass

    def Field(default: Any = None, **_kwargs: Any) -> Any: # type: ignore
        return default


# ==================== ENUMERATIONS ====================

class DocumentType(Enum):
    """Типы документов."""
    GENERAL = "general"
    REGULATORY = "regulatory"
    LEGAL = "legal"
    TECHNICAL = "technical"
    ADMINISTRATIVE = "administrative"
    PRESENTATION = "presentation"


class ProcessingStatus(Enum):
    """Статусы обработки."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==================== PYDANTIC MODELS ====================

class ValidationReport(BaseModel):
    """Отчет валидации для LangGraph workflow."""
    is_correct: bool = Field(description="Правильность извлеченных данных")
    critique: str = Field(description="Критика и оценка качества")
    suggestions_for_retry: Optional[str] = Field(None, description="Предложения для повторной попытки")


class SpatialElement(BaseModel):
    """Пространственный элемент на странице презентации."""
    element_id: str = Field(description="Уникальный идентификатор элемента")
    element_type: str = Field(description="Тип элемента: table, chart, map, text, image")
    position: Dict[str, Any] = Field(description="Пространственные координаты и размер")
    caption: Optional[str] = Field(None, description="Заголовок или подпись элемента")
    content_summary: Optional[str] = Field(None, description="Краткое описание содержимого")


class ElementRelationship(BaseModel):
    """Связь между элементами на странице."""
    from_element: str = Field(description="ID исходного элемента")
    to_element: str = Field(description="ID целевого элемента")
    relationship_type: str = Field(description="Тип связи: data_source, reference, summary, supports")
    confidence: float = Field(default=1.0, description="Уверенность в связи (0.0-1.0)")
    description: Optional[str] = Field(None, description="Описание характера связи")


class ContextualData(BaseModel):
    """Контекстуализированные извлеченные данные."""
    value: str = Field(description="Извлеченное значение или факт")
    source_element: str = Field(description="ID элемента-источника")
    context_description: str = Field(description="Описание контекста данного значения")
    related_elements: List[str] = Field(default_factory=list, description="Связанные элементы")
    spatial_context: Optional[str] = Field(None, description="Пространственный контекст (позиция на странице)")
    confidence_score: float = Field(default=1.0, description="Уверенность в извлечении (0.0-1.0)")
    data_type: Optional[str] = Field(None, description="Тип данных: numerical, textual, categorical")


class PageLayout(BaseModel):
    """Макет страницы с элементами и связями."""
    page_number: int = Field(description="Номер страницы")
    elements: List[SpatialElement] = Field(description="Элементы на странице")
    relationships: List[ElementRelationship] = Field(default_factory=list, description="Связи между элементами")
    layout_type: Optional[str] = Field(None, description="Тип макета: table_focused, chart_heavy, mixed")


class ContextualExtraction(BaseModel):
    """Полное контекстное извлечение со страницы."""
    page_number: int = Field(description="Номер страницы")
    page_layout: PageLayout = Field(description="Анализ макета страницы")
    extracted_data: List[ContextualData] = Field(description="Извлеченные контекстуализированные данные")
    summary: Optional[str] = Field(None, description="Общая сводка содержимого страницы")


class ParsedTable(BaseModel):
    """Распарсенная таблица с метаданными."""
    table_id: str = Field(description="Идентификатор таблицы")
    title: Optional[str] = Field(None, description="Заголовок таблицы")
    headers: List[str] = Field(description="Заголовки колонок")
    rows: List[Dict[str, Any]] = Field(description="Строки таблицы как список словарей")
    caption: Optional[str] = Field(None, description="Подпись к таблице")
    position: Optional[Dict[str, Any]] = Field(None, description="Позиция на странице")


class ParsedPageTables(BaseModel):
    """Коллекция всех таблиц на странице."""
    page_number: int = Field(description="Номер страницы")
    tables: List[ParsedTable] = Field(description="Список таблиц на странице")
    summary: Optional[str] = Field(None, description="Общая сводка по таблицам")


# ==================== DATACLASS MODELS ====================

@dataclass
class TextChunk:
    """
    Текстовый чанк документа.

    ВАЖНО: Содержит фрагменты документов БД для поиска и анализа
    (требование из complex_task.txt - использовать ТОЛЬКО документы БД)
    """
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class TableChunk:
    """Табличный чанк документа из БД."""
    id: str
    table_data: List[List[str]]
    headers: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class AnyChunk:
    """Универсальный чанк документа из БД."""
    id: str
    content: Any
    chunk_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class ExtractedData:
    """
    Извлеченные данные из документа БД.

    ВАЖНО: Эти данные извлечены из документов БД и используются
    для ответов системы (требование из complex_task.txt)
    """
    document_type: str
    document_number: str
    adoption_date: str
    issuing_authority: str
    summary: str
    key_requirements: List[str]
    scope: str
    related_documents: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Поля для контекстного анализа презентаций
    document_id: Optional[str] = field(default=None)
    source_filename: Optional[str] = field(default=None)
    chunks: List[Any] = field(default_factory=list)


@dataclass
class RegulatoryDocument:
    """Регулятивный документ из БД."""
    id: str
    file_path: str
    extracted_data: ExtractedData
    raw_text: str
    processing_status: str
    created_at: datetime
    duplicate: bool = False
    storage_result: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class Document:
    """
    Основная модель документа из БД.

    КРИТИЧЕСКИ ВАЖНО: Все документы загружаются в БД и используются
    системой для ответов, а НЕ собственные знания модели (complex_task.txt)
    """
    id: str
    file_path: str
    file_name: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    document_type: DocumentType = DocumentType.GENERAL
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[Union[TextChunk, TableChunk, AnyChunk]] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def add_chunk(self, chunk: Union[TextChunk, TableChunk, AnyChunk]):
        """Добавление чанка к документу из БД."""
        self.chunks.append(chunk)

    def get_text_content(self) -> str:
        """Получение всего текстового содержимого из БД."""
        text_parts = []
        for chunk in self.chunks:
            if isinstance(chunk, TextChunk):
                text_parts.append(chunk.text)
        return "\n\n".join(text_parts)


@dataclass
class ProcessingTask:
    """Задача обработки документов БД."""
    id: str
    task_type: str
    status: ProcessingStatus
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class ProcessingState:
    """Состояние процесса ingestion документов в БД."""
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    current_file: Optional[str] = None
    start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None

    @property
    def progress_percentage(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100


# ==================== LANGGRAPH STATE ====================

class IngestionState(TypedDict, total=False):
    """
    Состояние LangGraph workflow для контекстного извлечения презентаций.

    ВАЖНО: Workflow обрабатывает документы для загрузки в БД
    (требование из complex_task.txt - система должна использовать документы БД)
    """
    # Основные поля документа
    document_path: Optional[str]
    document_id: Optional[str]
    page_images: List[str]

    # Текущая страница
    current_page_index: int
    current_page_image: Optional[str]
    current_page_markdown: Optional[str]
    current_page_json_data: List[Dict[str, Any]]

    # Новые контекстные поля
    page_layout: Optional[PageLayout]
    contextual_data: Optional[ContextualData]
    enhanced_relationships: List[ElementRelationship]
    layout_analysis_raw: Optional[str]

    # Валидация и качество
    current_validation_report: Optional[ValidationReport]
    context_validation_score: Optional[float]
    context_quality_scores: List[float]
    validation_details: Optional[Dict[str, Any]]

    # Чанки и обработка
    chunks_per_page: Dict[int, List[AnyChunk]]
    retry_attempts: int

    # Статус и контроль
    status: Optional[str]
    error_message: Optional[str]
    relationship_analysis_summary: Optional[str]


# ==================== CONTEXTUAL CHUNK ====================

class ContextualChunk:
    """
    Контекстный чанк презентации с сохранением связей между элементами.

    КРИТИЧЕСКИ ВАЖНО: Эти чанки хранятся в БД и используются системой
    для ответов, а НЕ собственные знания модели (требование из complex_task.txt)
    """

    def __init__(
        self,
        slide_number: int,
        id: str = "",
        elements: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
        context_summary: str = "",
        key_insights: Optional[List[str]] = None,
        searchable_text: str = "",
        slide_title: Optional[str] = None,
        slide_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.slide_number = slide_number
        self.id = id
        self.elements = elements or []
        self.relationships = relationships or []
        self.context_summary = context_summary
        self.key_insights = key_insights or []
        self.searchable_text = searchable_text
        self.slide_title = slide_title
        self.slide_type = slide_type
        self.metadata = metadata or {}

        # Call post-init logic
        self.__post_init__()

    def __post_init__(self):
        if not self.id:
            self.id = f"contextual_slide_{self.slide_number}_{str(uuid.uuid4())[:8]}"

        # Автоматически генерируем searchable_text если он пустой
        if not self.searchable_text:
            self.searchable_text = self._generate_searchable_text()

    def _generate_searchable_text(self) -> str:
        """Генерирует объединенный текст для поиска из всех элементов и связей в БД."""
        text_parts = []

        # Заголовок слайда
        if self.slide_title:
            text_parts.append(f"Заголовок: {self.slide_title}")

        # Тип слайда
        if self.slide_type:
            text_parts.append(f"Тип: {self.slide_type}")

        # Краткое содержание контекста
        if self.context_summary:
            text_parts.append(f"Контекст: {self.context_summary}")

        # Ключевые идеи
        if self.key_insights:
            text_parts.append(f"Идеи: {'; '.join(self.key_insights)}")

        # Содержимое элементов
        for element in self.elements:
            if 'content_summary' in element and element['content_summary']:
                text_parts.append(f"Элемент: {element['content_summary']}")
            if 'caption' in element and element['caption']:
                text_parts.append(f"Подпись: {element['caption']}")

        # Описания связей
        for relationship in self.relationships:
            if 'description' in relationship and relationship['description']:
                text_parts.append(f"Связь: {relationship['description']}")

        return " | ".join(text_parts)