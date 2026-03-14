"""
Семантическое сжатие истории разговоров для правовых консультаций.
Сохраняет контекст, правовые концепции и уровень экспертизы пользователя.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import hashlib

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers не установлен. Будет использован базовый анализ.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("numpy не установлен. Семантический анализ ограничен.")

from .legal_ontology import LegalOntology, DocumentType
from .smart_query_classifier import SmartQueryClassifier, QueryType, UserExpertiseLevel

logger = logging.getLogger(__name__)

class MessageImportance(Enum):
    """Уровни важности сообщений в правовом контексте"""
    CRITICAL = "critical" # Ключевые правовые концепции, решения
    HIGH = "high" # Важные уточнения, ссылки на статьи
    MEDIUM = "medium" # Обычные вопросы и ответы
    LOW = "low" # Формальности, приветствия
    REDUNDANT = "redundant" # Дублирующая информация

@dataclass
class LegalConcept:
    """Правовая концепция из сообщения"""
    concept: str
    document_type: Optional[DocumentType]
    article_reference: Optional[str]
    confidence: float
    context: str

@dataclass
class CompressedMessage:
    """Сжатое представление сообщения"""
    original_timestamp: datetime
    message_type: str # 'user' или 'bot'
    importance: MessageImportance
    legal_concepts: List[LegalConcept]
    key_points: List[str]
    compressed_content: str
    semantic_hash: str
    user_expertise_indicator: Optional[UserExpertiseLevel]

@dataclass
class ConversationSummary:
    """Сводка разговора с правовым контекстом"""
    session_start: datetime
    session_end: datetime
    total_messages: int
    compressed_messages: int
    user_expertise_level: UserExpertiseLevel
    dominant_legal_areas: List[str]
    key_legal_concepts: List[LegalConcept]
    unresolved_questions: List[str]
    conversation_flow: str
    compression_ratio: float

class SemanticHistoryCompressor:
    """
    Система семантического сжатия истории разговоров для правовых консультаций.
    Сохраняет контекст, правовые концепции и адаптируется к уровню экспертизы пользователя.
    """

    def __init__(self):
        self.legal_ontology = LegalOntology()
        self.query_classifier = SmartQueryClassifier()

        # Инициализация модели семантических эмбеддингов
        self.model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Используем многоязычную модель для русского языка
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("Загружена модель sentence-transformers для семантического анализа")
            except Exception as e:
                logger.warning(f"Не удалось загрузить sentence-transformers: {e}")
                self.model = None

        # Пороги для семантического анализа
        self.similarity_threshold = 0.75 # Порог для обнаружения дублирования
        self.importance_threshold = 0.6 # Порог важности для сохранения

        # Регулярные выражения для поиска правовых ссылок
        self.legal_reference_patterns = [
            r'статья\s+(\d+)',
            r'ст\.\s*(\d+)',
            r'часть\s+(\d+)\s+статьи\s+(\d+)',
            r'ч\.\s*(\d+)\s+ст\.\s*(\d+)',
            r'пункт\s+(\d+)',
            r'п\.\s*(\d+)',
            r'федеральный\s+закон\s+?\s*(\d+[-\w]*)',
            r'кодекс\s+(\w+)',
            r'конституция',
            r'указ\s+президента',
            r'постановление\s+правительства'
        ]

    def _extract_legal_concepts(self, text: str) -> List[LegalConcept]:
        """Извлекает правовые концепции из текста"""
        concepts = []
        text_lower = text.lower()

        try:
            # Поиск ссылок на статьи и документы
            import re
            for pattern in self.legal_reference_patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    concept_text = match.group(0)
                    article_ref = match.group(1) if match.groups() else None

                    # Определение типа документа
                    doc_type = None
                    if any(word in concept_text for word in ['федеральный закон', 'фз']):
                        doc_type = DocumentType.FEDERAL_LAW
                    elif 'кодекс' in concept_text:
                        doc_type = DocumentType.CODE
                    elif 'конституция' in concept_text:
                        doc_type = DocumentType.CONSTITUTION
                    elif 'указ' in concept_text:
                        doc_type = DocumentType.DECREE
                    elif 'постановление' in concept_text:
                        doc_type = DocumentType.REGULATION

                    concept = LegalConcept(
                        concept=concept_text,
                        document_type=doc_type,
                        article_reference=article_ref,
                        confidence=0.8,
                        context=text[:200] + "..." if len(text) > 200 else text
                    )
                    concepts.append(concept)

            # Поиск правовых терминов из онтологии
            if hasattr(self.legal_ontology, 'legal_synonyms'):
                for category, terms in self.legal_ontology.legal_synonyms.items():
                    for term in terms:
                        if term.lower() in text_lower:
                            concept = LegalConcept(
                                concept=term,
                                document_type=None,
                                article_reference=None,
                                confidence=0.6,
                                context=text[:200] + "..." if len(text) > 200 else text
                            )
                            concepts.append(concept)

        except Exception as e:
            logger.warning(f"Ошибка при извлечении правовых концепций: {e}")

        return concepts

    def _calculate_message_importance(self, message: Dict[str, Any]) -> MessageImportance:
        """Определяет важность сообщения в правовом контексте"""
        content = message.get('content', '').lower()
        message_type = message.get('type', 'user')

        # Критически важные индикаторы
        critical_indicators = [
            'решение', 'постановление', 'приговор', 'определение',
            'конституционный суд', 'верховный суд', 'арбитражный суд',
            'нарушение закона', 'преступление', 'административное правонарушение'
        ]

        # Высокая важность
        high_indicators = [
            'статья', 'федеральный закон', 'кодекс', 'конституция',
            'право', 'обязанность', 'ответственность', 'наказание',
            'процедура', 'требование', 'условие'
        ]

        # Средняя важность
        medium_indicators = [
            'вопрос', 'разъяснение', 'пример', 'случай',
            'практика', 'применение', 'толкование'
        ]

        # Низкая важность
        low_indicators = [
            'спасибо', 'пожалуйста', 'привет', 'до свидания',
            'понятно', 'ясно', 'хорошо'
        ]

        # Проверка на критичность
        if any(indicator in content for indicator in critical_indicators):
            return MessageImportance.CRITICAL

        # Проверка на высокую важность
        if any(indicator in content for indicator in high_indicators):
            return MessageImportance.HIGH

        # Сообщения бота с правовой информацией важнее
        if message_type == 'bot' and len(content) > 100:
            return MessageImportance.HIGH

        # Проверка на среднюю важность
        if any(indicator in content for indicator in medium_indicators):
            return MessageImportance.MEDIUM

        # Проверка на низкую важность
        if any(indicator in content for indicator in low_indicators):
            return MessageImportance.LOW

        # По умолчанию средняя важность
        return MessageImportance.MEDIUM

    def _extract_key_points(self, content: str, importance: MessageImportance) -> List[str]:
        """Извлекает ключевые моменты из сообщения"""
        key_points = []

        try:
            # Разбиение на предложения
            sentences = content.split('.')
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

            # Для критических сообщений сохраняем больше деталей
            if importance == MessageImportance.CRITICAL:
                key_points = sentences[:5]
            elif importance == MessageImportance.HIGH:
                key_points = sentences[:3]
            elif importance == MessageImportance.MEDIUM:
                key_points = sentences[:2]
            else:
                key_points = sentences[:1]

            # Фильтрация по правовой значимости
            filtered_points = []
            for point in key_points:
                if any(term in point.lower() for term in [
                    'статья', 'закон', 'право', 'обязанность', 'ответственность',
                    'процедура', 'требование', 'нарушение', 'суд', 'решение'
                ]):
                    filtered_points.append(point)
                elif len(filtered_points) < 2: # Сохраняем минимум контекста
                    filtered_points.append(point)

            return filtered_points or key_points[:1] # Хотя бы один пункт

        except Exception as e:
            logger.warning(f"Ошибка при извлечении ключевых моментов: {e}")
            return [content[:100] + "..." if len(content) > 100 else content]

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет семантическое сходство между текстами"""
        if not self.model or not NUMPY_AVAILABLE:
            # Базовый анализ на основе общих слов
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            return intersection / union if union > 0 else 0.0

        try:
            embeddings = self.model.encode([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            logger.warning(f"Ошибка при вычислении семантического сходства: {e}")
            return 0.0

    def _generate_semantic_hash(self, content: str) -> str:
        """Генерирует семантический хеш для обнаружения дублирования"""
        # Нормализация текста
        normalized = content.lower().strip()
        # Удаление знаков препинания для лучшего сравнения
        import re
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Создание хеша
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]

    def _assess_user_expertise(self, messages: List[Dict[str, Any]]) -> UserExpertiseLevel:
        """Оценивает уровень правовой экспертизы пользователя по сообщениям"""
        user_messages = [msg for msg in messages if msg.get('type') == 'user']

        if not user_messages:
            return UserExpertiseLevel.BEGINNER

        total_score = 0
        message_count = len(user_messages)

        for message in user_messages:
            content = message.get('content', '').lower()

            # Индикаторы экспертного уровня
            expert_indicators = [
                'согласно статье', 'в соответствии с', 'на основании',
                'федеральный закон', 'кодекс', 'конституция',
                'судебная практика', 'правоприменение', 'юрисдикция',
                'процессуальное право', 'материальное право'
            ]

            # Индикаторы продвинутого уровня
            advanced_indicators = [
                'статья', 'закон', 'право', 'обязанность',
                'ответственность', 'процедура', 'суд', 'решение'
            ]

            # Индикаторы базового уровня
            basic_indicators = [
                'что делать', 'как быть', 'правильно ли',
                'можно ли', 'разрешено ли', 'законно ли'
            ]

            # Подсчет очков
            if any(indicator in content for indicator in expert_indicators):
                total_score += 3
            elif any(indicator in content for indicator in advanced_indicators):
                total_score += 2
            elif any(indicator in content for indicator in basic_indicators):
                total_score += 1

        # Расчет среднего уровня
        average_score = total_score / message_count if message_count > 0 else 0

        if average_score >= 2.5:
            return UserExpertiseLevel.EXPERT
        elif average_score >= 1.5:
            return UserExpertiseLevel.ADVANCED
        elif average_score >= 0.5:
            return UserExpertiseLevel.INTERMEDIATE
        else:
            return UserExpertiseLevel.BEGINNER

    def compress_message(self, message: Dict[str, Any]) -> CompressedMessage:
        """Сжимает отдельное сообщение с сохранением правового контекста"""
        content = message.get('content', '')
        message_type = message.get('type', 'user')
        timestamp = message.get('timestamp', datetime.now())

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except:
                timestamp = datetime.now()

        # Определение важности
        importance = self._calculate_message_importance(message)

        # Извлечение правовых концепций
        legal_concepts = self._extract_legal_concepts(content)

        # Извлечение ключевых моментов
        key_points = self._extract_key_points(content, importance)

        # Создание сжатого контента
        if importance in [MessageImportance.CRITICAL, MessageImportance.HIGH]:
            compressed_content = content # Сохраняем полностью
        elif importance == MessageImportance.MEDIUM:
            compressed_content = content[:300] + "..." if len(content) > 300 else content
        else:
            compressed_content = content[:100] + "..." if len(content) > 100 else content

        # Семантический хеш
        semantic_hash = self._generate_semantic_hash(content)

        # Индикатор экспертизы (для сообщений пользователя)
        expertise_indicator = None
        if message_type == 'user':
            expertise_indicator = self._assess_user_expertise([message])

        return CompressedMessage(
            original_timestamp=timestamp,
            message_type=message_type,
            importance=importance,
            legal_concepts=legal_concepts,
            key_points=key_points,
            compressed_content=compressed_content,
            semantic_hash=semantic_hash,
            user_expertise_indicator=expertise_indicator
        )

    def remove_redundancy(self, compressed_messages: List[CompressedMessage]) -> List[CompressedMessage]:
        """Удаляет избыточные сообщения на основе семантического анализа"""
        unique_messages = []
        seen_hashes = set()

        for message in compressed_messages:
            # Проверка на точное дублирование по хешу
            if message.semantic_hash in seen_hashes:
                continue

            # Проверка на семантическое дублирование
            is_duplicate = False
            for existing in unique_messages:
                similarity = self._calculate_semantic_similarity(
                    message.compressed_content,
                    existing.compressed_content
                )

                if similarity > self.similarity_threshold:
                    # Если новое сообщение важнее, заменяем старое
                    if message.importance.value == "critical" and existing.importance.value != "critical":
                        unique_messages.remove(existing)
                        break
                    else:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_messages.append(message)
                seen_hashes.add(message.semantic_hash)

        return unique_messages

    def create_conversation_summary(self, compressed_messages: List[CompressedMessage]) -> ConversationSummary:
        """Создает сводку разговора с правовым контекстом"""
        if not compressed_messages:
            return ConversationSummary(
                session_start=datetime.now(),
                session_end=datetime.now(),
                total_messages=0,
                compressed_messages=0,
                user_expertise_level=UserExpertiseLevel.BEGINNER,
                dominant_legal_areas=[],
                key_legal_concepts=[],
                unresolved_questions=[],
                conversation_flow="",
                compression_ratio=0.0
            )

        # Временные рамки
        session_start = min(msg.original_timestamp for msg in compressed_messages)
        session_end = max(msg.original_timestamp for msg in compressed_messages)

        # Анализ экспертизы пользователя
        user_messages = [msg for msg in compressed_messages if msg.message_type == 'user']
        if user_messages:
            user_expertise_level = self._assess_user_expertise([
                {'content': msg.compressed_content, 'type': 'user'}
                for msg in user_messages
            ])
        else:
            user_expertise_level = UserExpertiseLevel.BEGINNER

        # Сбор всех правовых концепций
        all_legal_concepts = []
        for msg in compressed_messages:
            all_legal_concepts.extend(msg.legal_concepts)

        # Группировка по правовым областям
        legal_areas = {}
        for concept in all_legal_concepts:
            if concept.document_type:
                area = concept.document_type.value
                legal_areas[area] = legal_areas.get(area, 0) + 1

        dominant_legal_areas = sorted(legal_areas.keys(), key=lambda x: legal_areas[x], reverse=True)[:3]

        # Ключевые концепции (наиболее встречающиеся)
        concept_counts = {}
        for concept in all_legal_concepts:
            key = f"{concept.concept}_{concept.article_reference or 'general'}"
            if key not in concept_counts:
                concept_counts[key] = concept
            else:
                concept_counts[key].confidence = max(concept_counts[key].confidence, concept.confidence)

        key_legal_concepts = sorted(
            concept_counts.values(),
            key=lambda x: x.confidence,
            reverse=True
        )[:5]

        # Неразрешенные вопросы (сообщения пользователя с вопросительными знаками без последующих ответов)
        unresolved_questions = []
        for i, msg in enumerate(compressed_messages):
            if (msg.message_type == 'user' and
                '?' in msg.compressed_content and
                (i == len(compressed_messages) - 1 or
                 compressed_messages[i + 1].message_type == 'user')):
                unresolved_questions.append(msg.compressed_content[:100] + "...")

        # Поток разговора
        conversation_flow_parts = []
        current_topic = None

        for msg in compressed_messages[-10:]: # Последние 10 сообщений
            if msg.legal_concepts:
                topic = msg.legal_concepts[0].concept
                if topic != current_topic:
                    conversation_flow_parts.append(topic)
                    current_topic = topic

        conversation_flow = " ".join(conversation_flow_parts[-5:]) # Последние 5 тем

        # Коэффициент сжатия (примерный)
        original_size = sum(len(msg.compressed_content) for msg in compressed_messages)
        compressed_size = len(conversation_flow) + sum(len(concept.concept) for concept in key_legal_concepts)
        compression_ratio = compressed_size / original_size if original_size > 0 else 0.0

        return ConversationSummary(
            session_start=session_start,
            session_end=session_end,
            total_messages=len(compressed_messages),
            compressed_messages=len(compressed_messages),
            user_expertise_level=user_expertise_level,
            dominant_legal_areas=dominant_legal_areas,
            key_legal_concepts=key_legal_concepts,
            unresolved_questions=unresolved_questions[:3], # Максимум 3
            conversation_flow=conversation_flow,
            compression_ratio=compression_ratio
        )

    async def compress_conversation_history(self, messages: List[Dict[str, Any]],
                                          max_compressed_messages: int = 10) -> Tuple[List[CompressedMessage], ConversationSummary]:
        """
        Сжимает полную историю разговора с сохранением правового контекста.

        Args:
            messages: Список сообщений для сжатия
            max_compressed_messages: Максимальное количество сжатых сообщений

        Returns:
            Tuple с сжатыми сообщениями и сводкой разговора
        """
        try:
            logger.info(f"Начало сжатия истории: {len(messages)} сообщений")

            # Сжатие отдельных сообщений
            compressed_messages = []
            for message in messages:
                try:
                    compressed = self.compress_message(message)
                    compressed_messages.append(compressed)
                except Exception as e:
                    logger.warning(f"Ошибка сжатия сообщения: {e}")
                    continue

            # Удаление избыточности
            unique_messages = self.remove_redundancy(compressed_messages)

            # Сортировка по важности и времени
            sorted_messages = sorted(
                unique_messages,
                key=lambda x: (
                    x.importance.value == "critical",
                    x.importance.value == "high",
                    x.original_timestamp
                ),
                reverse=True
            )

            # Ограничение количества сообщений
            final_messages = sorted_messages[:max_compressed_messages]

            # Создание сводки
            summary = self.create_conversation_summary(compressed_messages)

            logger.info(f"Сжатие завершено: {len(final_messages)} итоговых сообщений")

            return final_messages, summary

        except Exception as e:
            logger.error(f"Ошибка при сжатии истории разговора: {e}")
            return [], ConversationSummary(
                session_start=datetime.now(),
                session_end=datetime.now(),
                total_messages=0,
                compressed_messages=0,
                user_expertise_level=UserExpertiseLevel.BEGINNER,
                dominant_legal_areas=[],
                key_legal_concepts=[],
                unresolved_questions=[],
                conversation_flow="",
                compression_ratio=0.0
            )

    def to_context_string(self, compressed_messages: List[CompressedMessage],
                         summary: ConversationSummary) -> str:
        """Преобразует сжатую историю в строку контекста для AI модели"""
        context_parts = []

        # Сводка разговора
        context_parts.append(f"КОНТЕКСТ РАЗГОВОРА:")
        context_parts.append(f"Уровень экспертизы пользователя: {summary.user_expertise_level.value}")
        context_parts.append(f"Основные правовые области: {', '.join(summary.dominant_legal_areas)}")
        context_parts.append(f"Поток обсуждения: {summary.conversation_flow}")

        if summary.unresolved_questions:
            context_parts.append(f"Неразрешенные вопросы: {'; '.join(summary.unresolved_questions)}")

        # Ключевые правовые концепции
        if summary.key_legal_concepts:
            context_parts.append("\nКЛЮЧЕВЫЕ ПРАВОВЫЕ КОНЦЕПЦИИ:")
            for concept in summary.key_legal_concepts:
                concept_str = f"- {concept.concept}"
                if concept.article_reference:
                    concept_str += f" (статья {concept.article_reference})"
                if concept.document_type:
                    concept_str += f" [{concept.document_type.value}]"
                context_parts.append(concept_str)

        # Важные сообщения из истории
        context_parts.append("\nВАЖНЫЕ МОМЕНТЫ ИЗ ИСТОРИИ:")
        for msg in compressed_messages:
            if msg.importance in [MessageImportance.CRITICAL, MessageImportance.HIGH]:
                timestamp_str = msg.original_timestamp.strftime("%H:%M")
                msg_prefix = "" if msg.message_type == 'user' else ""
                context_parts.append(f"{timestamp_str} {msg_prefix}: {msg.compressed_content[:200]}...")

                if msg.key_points:
                    for point in msg.key_points[:2]: # Максимум 2 ключевых момента
                        context_parts.append(f" • {point}")

        return "\n".join(context_parts)

    def export_compressed_history(self, compressed_messages: List[CompressedMessage],
                                 summary: ConversationSummary) -> Dict[str, Any]:
        """Экспортирует сжатую историю в JSON формат"""
        return {
            'summary': asdict(summary),
            'compressed_messages': [asdict(msg) for msg in compressed_messages],
            'compression_metadata': {
                'total_original_messages': summary.total_messages,
                'compressed_to': len(compressed_messages),
                'compression_ratio': summary.compression_ratio,
                'processed_at': datetime.now().isoformat()
            }
        }

# Глобальный экземпляр для использования в других модулях
semantic_compressor = SemanticHistoryCompressor()