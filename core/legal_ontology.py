#!/usr/bin/env python3
"""
⚖️ Legal Ontology Module
Модуль правовой онтологии для понимания структуры российского права.

Обеспечивает:
- Иерархию нормативных актов
- Словарь правовых терминов и синонимов
- Классификацию документов по типам
- Понимание правовых связей и отношений
"""

import logging
import re
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Типы правовых документов с приоритетами."""
    CONSTITUTION = "constitution"
    FEDERAL_LAW = "federal_law"
    CODE = "code"
    PRESIDENTIAL_DECREE = "presidential_decree"
    GOVERNMENT_RESOLUTION = "government_resolution"
    MINISTERIAL_ORDER = "ministerial_order"
    TECHNICAL_STANDARD = "technical_standard"
    REGIONAL_LAW = "regional_law"
    MUNICIPAL_ACT = "municipal_act"
    OTHER = "other"


class LegalDomain(Enum):
    """Правовые отрасли."""
    CIVIL = "civil"
    CRIMINAL = "criminal"
    ADMINISTRATIVE = "administrative"
    CONSTITUTIONAL = "constitutional"
    TAX = "tax"
    LABOR = "labor"
    ENVIRONMENTAL = "environmental"
    CONSTRUCTION = "construction"
    PROCUREMENT = "procurement"
    TECHNICAL = "technical"
    GENERAL = "general"


@dataclass
class LegalReference:
    """Структурированная ссылка на правовую норму."""
    document_type: DocumentType
    document_name: str
    article: Optional[str] = None
    paragraph: Optional[str] = None
    subparagraph: Optional[str] = None
    confidence: float = 1.0


@dataclass
class DocumentMetadata:
    """Метаданные правового документа."""
    document_type: DocumentType
    hierarchy_level: int
    legal_domain: LegalDomain
    adoption_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    is_active: bool = True


class LegalOntology:
    """
    Правовая онтология для понимания структуры российского права.

    Содержит знания о:
    - Иерархии нормативных актов
    - Правовой терминологии
    - Типах документов
    - Отраслевой специфике
    """

    # Иерархия документов (1 - высший уровень)
    DOCUMENT_HIERARCHY = {
        DocumentType.CONSTITUTION: 1,
        DocumentType.FEDERAL_LAW: 2,
        DocumentType.CODE: 2,
        DocumentType.PRESIDENTIAL_DECREE: 3,
        DocumentType.GOVERNMENT_RESOLUTION: 4,
        DocumentType.MINISTERIAL_ORDER: 5,
        DocumentType.TECHNICAL_STANDARD: 6,
        DocumentType.REGIONAL_LAW: 7,
        DocumentType.MUNICIPAL_ACT: 8,
        DocumentType.OTHER: 9
    }

    # Ключевые слова для типов документов
    DOCUMENT_TYPE_KEYWORDS = {
        DocumentType.CONSTITUTION: [
            "конституция", "конституционный"
        ],
        DocumentType.FEDERAL_LAW: [
            "федеральный закон", "фз", "n.*фз", "№.*фз",
            "закон российской федерации"
        ],
        DocumentType.CODE: [
            "кодекс", "гражданский кодекс", "гк рф", "уголовный кодекс", "ук рф",
            "административный кодекс", "коап", "налоговый кодекс", "нк рф",
            "трудовой кодекс", "тк рф", "семейный кодекс", "ск рф"
        ],
        DocumentType.PRESIDENTIAL_DECREE: [
            "указ президента", "указ", "президентский указ"
        ],
        DocumentType.GOVERNMENT_RESOLUTION: [
            "постановление правительства", "постановление", "правительственное постановление"
        ],
        DocumentType.MINISTERIAL_ORDER: [
            "приказ", "ведомственный приказ", "приказ министерства",
            "приказ минстроя", "приказ минэкономразвития"
        ],
        DocumentType.TECHNICAL_STANDARD: [
            "сп ", "гост", "снип", "санпин", "одм", "всн", "рд",
            "строительные правила", "государственный стандарт",
            "санитарные правила", "технический регламент"
        ]
    }

    # Словарь правовых синонимов
    LEGAL_SYNONYMS = {
        # Договорная терминология
        "договор": ["соглашение", "контракт", "сделка"],
        "соглашение": ["договор", "контракт", "сделка"],
        "контракт": ["договор", "соглашение", "сделка"],

        # Ответственность
        "ответственность": ["санкции", "наказание", "взыскание", "штраф"],
        "санкции": ["ответственность", "наказание", "взыскание"],
        "штраф": ["взыскание", "санкции", "денежное взыскание"],

        # Требования и нормы
        "требования": ["нормы", "стандарты", "правила", "нормативы"],
        "нормы": ["требования", "стандарты", "правила", "нормативы"],
        "стандарты": ["требования", "нормы", "правила", "нормативы"],
        "правила": ["требования", "нормы", "стандарты", "нормативы"],

        # Процедуры
        "процедура": ["порядок", "алгоритм", "последовательность"],
        "порядок": ["процедура", "алгоритм", "последовательность"],

        # Разрешения
        "разрешение": ["лицензия", "допуск", "согласование"],
        "лицензия": ["разрешение", "допуск"],
        "согласование": ["разрешение", "одобрение"],

        # Строительство
        "строительство": ["возведение", "строительные работы"],
        "возведение": ["строительство", "строительные работы"],

        # Теплоснабжение
        "теплоснабжение": ["отопление", "тепловое снабжение", "централизованное теплоснабжение"],
        "отопление": ["теплоснабжение", "обогрев"],
        "тепловая энергия": ["теплота", "тепловая мощность"],

        # Государственные закупки
        "государственные закупки": ["госзакупки", "публичные закупки", "закупки"],
        "госзакупки": ["государственные закупки", "публичные закупки"],
        "контрактная система": ["система госзакупок", "закупочная система"]
    }

    # Аббревиатуры и сокращения
    ABBREVIATIONS = {
        "гк рф": ["гражданский кодекс российской федерации", "гражданский кодекс"],
        "ук рф": ["уголовный кодекс российской федерации", "уголовный кодекс"],
        "коап рф": ["кодекс российской федерации об административных правонарушениях"],
        "тк рф": ["трудовой кодекс российской федерации", "трудовой кодекс"],
        "нк рф": ["налоговый кодекс российской федерации", "налоговый кодекс"],
        "грк рф": ["градостроительный кодекс российской федерации"],
        "44-фз": ["федеральный закон о контрактной системе", "закон о госзакупках"],
        "223-фз": ["федеральный закон о закупках отдельными видами юридических лиц"],
        "рф": ["российская федерация", "россия"],
        "сп": ["строительные правила", "свод правил"],
        "гост": ["государственный стандарт"],
        "снип": ["строительные нормы и правила"],
        "санпин": ["санитарные правила и нормы"]
    }

    # Паттерны для извлечения ссылок на статьи
    ARTICLE_PATTERNS = [
        r"стать[яеи]\s*(\d+(?:\.\d+)*)",
        r"ст\.\s*(\d+(?:\.\d+)*)",
        r"статья\s*(\d+(?:\.\d+)*)",
        r"статье\s*(\d+(?:\.\d+)*)",
        r"пункт\s*(\d+(?:\.\d+)*)\s*стать[еия]\s*(\d+)",
        r"п\.\s*(\d+(?:\.\d+)*)\s*ст\.\s*(\d+)",
        r"подпункт\s*(\w+)\s*пункта\s*(\d+)\s*стать[еия]\s*(\d+)"
    ]

    def __init__(self):
        """Инициализация правовой онтологии."""
        self.document_cache = {}
        self.reference_cache = {}
        logger.info("✅ Legal Ontology инициализирована")

    def get_document_hierarchy_level(self, document_type: DocumentType) -> int:
        """Получение уровня иерархии документа."""
        return self.DOCUMENT_HIERARCHY.get(document_type, 9)

    def classify_document_type(self, text: str) -> Tuple[DocumentType, float]:
        """
        Классификация типа документа по тексту.

        Args:
            text: Текст документа или его описание

        Returns:
            Tuple[DocumentType, confidence_score]
        """
        text_lower = text.lower()

        best_type = DocumentType.OTHER
        best_score = 0.0

        for doc_type, keywords in self.DOCUMENT_TYPE_KEYWORDS.items():
            score = 0.0

            for keyword in keywords:
                if re.search(keyword, text_lower):
                    # Точное совпадение дает больший вес
                    if keyword in text_lower:
                        score += 1.0
                    else:
                        score += 0.7

            # Нормализация по количеству ключевых слов
            normalized_score = score / len(keywords) if keywords else 0

            if normalized_score > best_score:
                best_score = normalized_score
                best_type = doc_type

        return best_type, min(best_score, 1.0)

    def extract_legal_references(self, text: str) -> List[LegalReference]:
        """
        Извлечение ссылок на правовые нормы из текста.

        Args:
            text: Текст для анализа

        Returns:
            Список найденных правовых ссылок
        """
        references = []
        text_lower = text.lower()
        found_spans = set()  # Для избежания дублирования

        # Поиск ссылок на статьи
        for pattern in self.ARTICLE_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)

            for match in matches:
                # Проверяем, не перекрывается ли с уже найденным
                span = (match.start(), match.end())
                overlapping = any(
                    (span[0] < existing[1] and span[1] > existing[0])
                    for existing in found_spans
                )

                if overlapping:
                    continue

                found_spans.add(span)
                groups = match.groups()

                if len(groups) == 1:
                    # Простая ссылка на статью
                    article = groups[0]
                    doc_type, confidence = self._guess_document_type_from_context(
                        text, match.start(), match.end()
                    )

                    references.append(LegalReference(
                        document_type=doc_type,
                        document_name="",
                        article=article,
                        confidence=confidence
                    ))

                elif len(groups) == 2:
                    # Ссылка с пунктом
                    paragraph, article = groups
                    doc_type, confidence = self._guess_document_type_from_context(
                        text, match.start(), match.end()
                    )

                    references.append(LegalReference(
                        document_type=doc_type,
                        document_name="",
                        article=article,
                        paragraph=paragraph,
                        confidence=confidence
                    ))

        return references

    def expand_synonyms(self, query: str) -> List[str]:
        """
        Расширение запроса синонимами.

        Args:
            query: Исходный запрос

        Returns:
            Список запросов с синонимами
        """
        expanded_queries = [query]
        query_lower = query.lower()

        # Поиск синонимов
        for term, synonyms in self.LEGAL_SYNONYMS.items():
            if term in query_lower:
                for synonym in synonyms:
                    expanded_query = query_lower.replace(term, synonym)
                    expanded_queries.append(expanded_query)

        # Расшифровка аббревиатур
        for abbr, expansions in self.ABBREVIATIONS.items():
            if abbr in query_lower:
                for expansion in expansions:
                    expanded_query = query_lower.replace(abbr, expansion)
                    expanded_queries.append(expanded_query)

        return list(set(expanded_queries))  # Удаляем дубликаты

    def get_legal_domain(self, text: str) -> Tuple[LegalDomain, float]:
        """
        Определение правовой отрасли по тексту.

        Args:
            text: Текст для анализа

        Returns:
            Tuple[LegalDomain, confidence_score]
        """
        text_lower = text.lower()

        domain_keywords = {
            LegalDomain.CIVIL: [
                "гражданский", "гк рф", "договор", "собственность", "обязательства"
            ],
            LegalDomain.CRIMINAL: [
                "уголовный", "ук рф", "преступление", "наказание"
            ],
            LegalDomain.ADMINISTRATIVE: [
                "административный", "коап", "правонарушение", "штраф"
            ],
            LegalDomain.TAX: [
                "налоговый", "нк рф", "налог", "сбор", "пошлина"
            ],
            LegalDomain.LABOR: [
                "трудовой", "тк рф", "трудовые отношения", "работник"
            ],
            LegalDomain.CONSTRUCTION: [
                "строительство", "градостроительный", "грк рф", "сп ", "снип", "гост"
            ],
            LegalDomain.PROCUREMENT: [
                "закупки", "44-фз", "223-фз", "контрактная система", "госзакупки"
            ],
            LegalDomain.TECHNICAL: [
                "технический", "стандарт", "требования", "параметры"
            ]
        }

        best_domain = LegalDomain.GENERAL
        best_score = 0.0

        for domain, keywords in domain_keywords.items():
            score = sum(1.0 for keyword in keywords if keyword in text_lower)
            normalized_score = score / len(keywords) if keywords else 0

            if normalized_score > best_score:
                best_score = normalized_score
                best_domain = domain

        return best_domain, min(best_score, 1.0)

    def compare_document_significance(self, doc1_type: DocumentType, doc2_type: DocumentType) -> int:
        """
        Сравнение значимости документов по иерархии.

        Args:
            doc1_type: Тип первого документа
            doc2_type: Тип второго документа

        Returns:
            -1 если doc1 важнее, 1 если doc2 важнее, 0 если равны
        """
        level1 = self.get_document_hierarchy_level(doc1_type)
        level2 = self.get_document_hierarchy_level(doc2_type)

        if level1 < level2:
            return -1
        elif level1 > level2:
            return 1
        else:
            return 0

    def _guess_document_type_from_context(self, text: str, start: int, end: int) -> Tuple[DocumentType, float]:
        """
        Угадывание типа документа по контексту вокруг ссылки.

        Args:
            text: Полный текст
            start: Начальная позиция ссылки
            end: Конечная позиция ссылки

        Returns:
            Tuple[DocumentType, confidence]
        """
        # Анализируем контекст в радиусе 100 символов
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        context = text[context_start:context_end].lower()

        # Специальные паттерны для известных документов
        specific_patterns = {
            DocumentType.CODE: [
                "трудового кодекса", "трудовой кодекс", "тк рф",
                "гражданского кодекса", "гражданский кодекс", "гк рф",
                "уголовного кодекса", "уголовный кодекс", "ук рф",
                "налогового кодекса", "налоговый кодекс", "нк рф",
                "кодекса об административных", "коап рф"
            ],
            DocumentType.CONSTITUTION: [
                "конституции", "конституция", "основного закона"
            ],
            DocumentType.FEDERAL_LAW: [
                "федерального закона", "федеральный закон", "фз", "-фз"
            ]
        }

        # Проверяем специальные паттерны
        for doc_type, patterns in specific_patterns.items():
            for pattern in patterns:
                if pattern in context:
                    return doc_type, 0.9

        # Ищем упоминания типов документов в контексте
        for doc_type, keywords in self.DOCUMENT_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in context:
                    return doc_type, 0.8

        return DocumentType.OTHER, 0.3

    def is_legal_query(self, query: str) -> Tuple[bool, float]:
        """
        Определение, является ли запрос правовым.

        Args:
            query: Запрос для анализа

        Returns:
            Tuple[is_legal, confidence]
        """
        query_lower = query.lower()

        legal_indicators = [
            # Прямые правовые термины
            "закон", "статья", "кодекс", "право", "требования",
            "ответственность", "нарушение", "порядок", "процедура",
            "разрешение", "лицензия", "регулирование", "норма",

            # Аббревиатуры
            "гк рф", "ук рф", "коап", "тк рф", "нк рф", "грк рф",
            "44-фз", "223-фз", "фз", "сп ", "гост", "снип",

            # Отраслевые термины
            "договор", "контракт", "соглашение", "штраф", "санкции",
            "строительство", "теплоснабжение", "закупки"
        ]

        score = 0.0
        for indicator in legal_indicators:
            if indicator in query_lower:
                score += 1.0

        # Нормализация
        normalized_score = min(score / 5.0, 1.0)  # Максимум 5 индикаторов для 100%

        is_legal = normalized_score > 0.2  # Порог 20%

        return is_legal, normalized_score


# Глобальный экземпляр онтологии
_legal_ontology = None

def get_legal_ontology() -> LegalOntology:
    """Получение глобального экземпляра правовой онтологии."""
    global _legal_ontology
    if _legal_ontology is None:
        _legal_ontology = LegalOntology()
    return _legal_ontology


if __name__ == "__main__":
    # Демонстрация возможностей модуля
    print("⚖️ Legal Ontology - Демонстрация")
    print("=" * 50)

    ontology = LegalOntology()

    # Тестовые запросы
    test_queries = [
        "Статья 51 ГрК РФ о разрешениях на строительство",
        "44-ФЗ о госзакупках",
        "Требования СП к отоплению зданий",
        "Привет, как дела?"
    ]

    for query in test_queries:
        print(f"\n🔍 Запрос: {query}")

        # Классификация правового содержания
        is_legal, confidence = ontology.is_legal_query(query)
        print(f"   Правовой запрос: {'Да' if is_legal else 'Нет'} (уверенность: {confidence:.2f})")

        # Определение отрасли права
        domain, domain_conf = ontology.get_legal_domain(query)
        print(f"   Отрасль права: {domain.value} (уверенность: {domain_conf:.2f})")

        # Извлечение ссылок
        references = ontology.extract_legal_references(query)
        if references:
            print(f"   Найдено ссылок: {len(references)}")
            for ref in references[:2]:  # Показываем первые 2
                print(f"     - {ref.document_type.value}, статья {ref.article}")

        # Расширение синонимами
        expanded = ontology.expand_synonyms(query)
        if len(expanded) > 1:
            print(f"   Синонимы найдены: {len(expanded) - 1}")