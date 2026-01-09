#!/usr/bin/env python3
"""
🔍 Search Service Utilities
Утилитарные функции для микросервиса поиска.

Включает функциональность:
- Обработка и форматирование текста
- Извлечение ключевых предложений
- Форматирование правовых ссылок
- Обработка дат и времени
- Вычисление релевантности
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class SearchUtilities:
    """Утилитарные функции для поисковых операций."""

    @staticmethod
    def _extract_key_sentences(text: str, max_sentences: int = 3) -> str:
        """Извлечение ключевых предложений из текста."""
        try:
            if not text or not text.strip():
                return ""

            # Разбиваем текст на предложения
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]

            if not sentences:
                return text[:200] + "..." if len(text) > 200 else text

            # Приоритизируем предложения с правовыми терминами
            legal_keywords = [
                'статья', 'закон', 'федеральный', 'постановление', 'приказ',
                'договор', 'соглашение', 'обязательство', 'право', 'ответственность',
                'штраф', 'нарушение', 'требование', 'процедура', 'порядок'
            ]

            scored_sentences = []
            for sentence in sentences:
                score = 0
                sentence_lower = sentence.lower()

                # Бонус за правовые термины
                for keyword in legal_keywords:
                    if keyword in sentence_lower:
                        score += 2

                # Бонус за цифры (статьи, пункты)
                if re.search(r'\d+', sentence):
                    score += 1

                # Бонус за длину (информативность)
                if 50 <= len(sentence) <= 300:
                    score += 1

                # Штраф за слишком короткие или длинные предложения
                if len(sentence) < 30 or len(sentence) > 500:
                    score -= 1

                scored_sentences.append((sentence, score))

            # Сортируем по релевантности
            scored_sentences.sort(key=lambda x: x[1], reverse=True)

            # Берем топ предложений
            selected = [sent[0] for sent in scored_sentences[:max_sentences]]

            return '. '.join(selected) + '.' if selected else text[:200] + "..."

        except Exception as e:
            logger.error(f"❌ Ошибка извлечения ключевых предложений: {e}")
            return text[:200] + "..." if len(text) > 200 else text

    @staticmethod
    def _compose_contextual_answer(query: str, chunks: List[Dict], legal_context: Dict = None) -> str:
        """Составление контекстуального ответа на основе найденных фрагментов."""
        try:
            if not chunks:
                return "По вашему запросу не найдено релевантной информации в загруженных документах."

            # Извлекаем и обрабатываем тексты
            processed_chunks = []
            seen_texts = set()

            for chunk in chunks[:5]:  # Берем топ-5 результатов
                text = chunk.get('text', chunk.get('document', ''))
                if not text or text in seen_texts:
                    continue

                seen_texts.add(text)

                # Извлекаем ключевые предложения
                key_sentences = SearchUtilities._extract_key_sentences(text, max_sentences=2)

                # Добавляем метаданные
                metadata = chunk.get('metadata', {})
                law_reference = SearchUtilities._format_law_reference(metadata)

                processed_chunks.append({
                    'text': key_sentences,
                    'law_reference': law_reference,
                    'similarity': chunk.get('similarity', 0)
                })

            if not processed_chunks:
                return "Найденные документы не содержат релевантной информации по вашему запросу."

            # Формируем структурированный ответ
            answer_parts = []

            # Основной ответ на основе самого релевантного фрагмента
            best_chunk = processed_chunks[0]
            answer_parts.append(f"**Ответ по вашему запросу:**\n{best_chunk['text']}")

            # Добавляем ссылку на источник
            if best_chunk['law_reference']:
                answer_parts.append(f"\n**Источник:** {best_chunk['law_reference']}")

            # Дополнительная информация из других фрагментов
            if len(processed_chunks) > 1:
                additional_info = []
                for chunk in processed_chunks[1:3]:  # Еще 2 фрагмента
                    if chunk['text'] and chunk['text'] != best_chunk['text']:
                        info = chunk['text']
                        if chunk['law_reference']:
                            info += f" (Источник: {chunk['law_reference']})"
                        additional_info.append(info)

                if additional_info:
                    answer_parts.append(f"\n**Дополнительная информация:**\n" +
                                      "\n\n".join(f"• {info}" for info in additional_info))

            # Добавляем правовой контекст если есть
            if legal_context and legal_context.get('entities'):
                entities = legal_context['entities'][:3]  # Топ-3 сущности
                if entities:
                    answer_parts.append(f"\n**Связанные правовые понятия:** {', '.join(entities)}")

            return '\n'.join(answer_parts)

        except Exception as e:
            logger.error(f"❌ Ошибка составления контекстуального ответа: {e}")
            return "Произошла ошибка при формировании ответа. Попробуйте переформулировать запрос."

    @staticmethod
    def _format_law_reference(metadata: Dict) -> str:
        """Форматирование ссылки на правовой документ."""
        try:
            if not metadata:
                return ""

            # Извлекаем информацию о документе
            law_number = metadata.get('law_number', metadata.get('document_number', ''))
            law_type = metadata.get('law_type', metadata.get('document_type', ''))
            article = metadata.get('article', metadata.get('article_number', ''))
            chapter = metadata.get('chapter', '')
            paragraph = metadata.get('paragraph', '')

            reference_parts = []

            # Формируем основную ссылку
            if law_number:
                if 'ФЗ' in law_number or 'фз' in law_number.lower():
                    reference_parts.append(f"Федеральный закон {law_number}")
                elif law_type:
                    reference_parts.append(f"{law_type} {law_number}")
                else:
                    reference_parts.append(law_number)

            # Добавляем детализацию
            details = []
            if chapter:
                details.append(f"глава {chapter}")
            if article:
                details.append(f"статья {article}")
            if paragraph:
                details.append(f"пункт {paragraph}")

            if details:
                reference_parts.append(f"({', '.join(details)})")

            return ' '.join(reference_parts) if reference_parts else ""

        except Exception as e:
            logger.error(f"❌ Ошибка форматирования правовой ссылки: {e}")
            return ""

    @staticmethod
    def verify_citation_exists(text: str, metadata: Dict[str, Any]) -> bool:
        """Проверка, что упомянутая статья реально присутствует в тексте фрагмента.

        Возвращает True, если либо нет ссылки, либо ссылка валидна; False если указана статья, но паттерн не найден.
        """
        try:
            if not text or not metadata:
                return True

            article = str(metadata.get('article') or metadata.get('article_number') or '').strip()
            if not article:
                return True

            # Ищем "статья <номер>" или варианты падежей/форматов
            pattern = rf"стат(?:ья|и|ей)\s+{re.escape(article)}(\b|\.)"
            return re.search(pattern, text, re.IGNORECASE) is not None
        except Exception as e:
            logger.error(f"❌ Ошибка верификации цитаты: {e}")
            return True

    @staticmethod
    def _calculate_recency_bonus(document_date: str, max_bonus: float = 0.1) -> float:
        """Вычисление бонуса за актуальность документа."""
        try:
            if not document_date:
                return 0.0

            # Парсим дату документа
            doc_date = SearchUtilities._parse_document_date(document_date)
            if not doc_date:
                return 0.0

            # Вычисляем возраст документа в днях
            today = datetime.now().date()
            age_days = (today - doc_date).days

            # Бонус убывает с возрастом
            if age_days <= 30:  # Очень свежий документ
                return max_bonus
            elif age_days <= 365:  # Документ до года
                return max_bonus * (1 - age_days / 365) * 0.8
            elif age_days <= 365 * 3:  # Документ до 3 лет
                return max_bonus * 0.2
            else:  # Старый документ
                return 0.0

        except Exception as e:
            logger.error(f"❌ Ошибка вычисления бонуса актуальности: {e}")
            return 0.0

    @staticmethod
    def _parse_document_date(date_string: str) -> Optional[datetime.date]:
        """Парсинг даты документа из различных форматов."""
        try:
            if not date_string:
                return None

            # Очищаем строку
            cleaned_date = re.sub(r'[^\d\-\.\s/]', '', str(date_string))

            # Попытки парсинга в различных форматах
            formats = [
                '%Y-%m-%d',
                '%d.%m.%Y',
                '%d/%m/%Y',
                '%Y.%m.%d',
                '%d-%m-%Y'
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(cleaned_date.strip(), fmt).date()
                except ValueError:
                    continue

            # Последняя попытка с dateutil
            try:
                return date_parser.parse(cleaned_date, dayfirst=True).date()
            except:
                pass

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга даты '{date_string}': {e}")
            return None

    @staticmethod
    def _get_storage_stats(storage_manager) -> Dict[str, Any]:
        """Получение статистики хранилища."""
        try:
            stats = {
                "total_documents": 0,
                "vector_store_status": "unknown",
                "postgres_status": "unknown",
                "redis_status": "unknown"
            }

            if not storage_manager:
                return stats

            # Статистика векторного хранилища
            if hasattr(storage_manager, 'vector_store') and storage_manager.vector_store:
                try:
                    vs_stats = storage_manager.vector_store.get_collection_stats()
                    stats["total_documents"] = vs_stats.get("total_documents", 0)
                    stats["vector_store_status"] = "connected"
                    stats["collection_name"] = vs_stats.get("collection_name", "unknown")
                except Exception as e:
                    stats["vector_store_status"] = f"error: {e}"

            # Статистика PostgreSQL
            if hasattr(storage_manager, 'postgres') and storage_manager.postgres:
                try:
                    if hasattr(storage_manager.postgres, 'pool') and storage_manager.postgres.pool:
                        stats["postgres_status"] = "connected"
                        stats["postgres_pool_size"] = len(storage_manager.postgres.pool._holders)
                    else:
                        stats["postgres_status"] = "disconnected"
                except Exception as e:
                    stats["postgres_status"] = f"error: {e}"

            # Статистика Redis
            if hasattr(storage_manager, 'redis') and storage_manager.redis:
                try:
                    if hasattr(storage_manager.redis, 'client') and storage_manager.redis.client:
                        stats["redis_status"] = "connected"
                    else:
                        stats["redis_status"] = "disconnected"
                except Exception as e:
                    stats["redis_status"] = f"error: {e}"

            return stats

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики хранилища: {e}")
            return {"error": str(e)}

    @staticmethod
    def enhance_query_with_legal_terms(query: str) -> str:
        """Улучшение запроса правовыми терминами."""
        try:
            # Словарь синонимов для правовых терминов
            legal_synonyms = {
                'штраф': ['санкция', 'взыскание', 'пеня'],
                'договор': ['соглашение', 'контракт'],
                'закон': ['нормативный акт', 'законодательство'],
                'ответственность': ['обязательство', 'санкция'],
                'право': ['полномочие', 'возможность'],
                'процедура': ['порядок', 'процесс', 'механизм']
            }

            enhanced_query = query.lower()

            # Добавляем синонимы для найденных терминов
            for term, synonyms in legal_synonyms.items():
                if term in enhanced_query:
                    # Добавляем наиболее релевантный синоним
                    enhanced_query += f" {synonyms[0]}"

            return enhanced_query

        except Exception as e:
            logger.error(f"❌ Ошибка улучшения запроса: {e}")
            return query

    @staticmethod
    def extract_legal_entities(text: str) -> List[str]:
        """Извлечение правовых сущностей из текста."""
        try:
            entities = []

            # Паттерны для правовых сущностей
            patterns = {
                'законы': r'(?:федеральный\s+)?закон\s+(?:от\s+)?№?\s*(\d+(?:-\w+)?)',
                'статьи': r'стат(?:ь|ья|ей)\s+(\d+(?:\.\d+)?)',
                'пункты': r'пункт(?:а|е)?\s+(\d+(?:\.\d+)?)',
                'главы': r'глав(?:а|е|ы)\s+(\d+|\w+)'
            }

            for entity_type, pattern in patterns.items():
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    entities.append(f"{entity_type}: {match}")

            return entities[:10]  # Ограничиваем количество

        except Exception as e:
            logger.error(f"❌ Ошибка извлечения правовых сущностей: {e}")
            return []