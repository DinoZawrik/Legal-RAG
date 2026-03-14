#!/usr/bin/env python3
"""
Smart Query Classifier
Умная система классификации запросов с NLP-анализом и правовой логикой.

Обеспечивает:
- Продвинутую классификацию типов запросов
- Анализ правовых интенций
- Контекстное понимание запросов
- Интеграцию с правовой онтологией
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

from core.legal_ontology import get_legal_ontology, LegalDomain, DocumentType
from core.advanced_prompts import QueryType

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Интенции правовых запросов."""
    FIND_NORM = "find_norm" # Найти конкретную норму
    EXPLAIN_PROCEDURE = "explain_procedure" # Объяснить процедуру
    COMPARE_REQUIREMENTS = "compare_requirements" # Сравнить требования
    FIND_RESPONSIBILITY = "find_responsibility" # Найти ответственность
    GET_DEFINITION = "get_definition" # Получить определение
    CALCULATE_PARAMETERS = "calculate_parameters" # Расчитать параметры
    FIND_CONFLICTS = "find_conflicts" # Найти коллизии
    GENERAL_CONSULTATION = "general_consultation" # Общая консультация
    CASUAL_CHAT = "casual_chat" # Обычное общение


class QueryComplexity(Enum):
    """Сложность запроса."""
    SIMPLE = "simple" # Простой вопрос
    MEDIUM = "medium" # Средней сложности
    COMPLEX = "complex" # Сложный вопрос
    EXPERT = "expert" # Экспертный уровень


class UserExpertiseLevel(Enum):
    """Уровень правовой экспертизы пользователя."""
    BEGINNER = "beginner" # Начинающий (без юридического образования)
    INTERMEDIATE = "intermediate" # Базовые знания (студенты, смежные профессии)
    ADVANCED = "advanced" # Продвинутый (практикующие юристы)
    EXPERT = "expert" # Эксперт (опытные юристы, судьи)


@dataclass
class QueryAnalysis:
    """Результат анализа запроса."""
    query_type: QueryType
    user_expertise: UserExpertiseLevel
    complexity: str
    intent: QueryIntent = QueryIntent.GENERAL_CONSULTATION
    legal_area: Optional[str] = None
    key_concepts: List[str] = None
    intent_confidence: float = 0.8

    def __post_init__(self):
        if self.key_concepts is None:
            self.key_concepts = []


@dataclass
class ContextualQueryAnalysis:
    """Анализ запроса с учетом контекста разговора."""
    base_analysis: QueryAnalysis
    context_references: List[str]
    continuing_topic: bool
    topic_shift: bool
    requires_clarification: bool
    related_queries: List[str]


class SmartQueryClassifier:
    """
    Умная система классификации запросов с NLP-анализом.

    Функции:
    - Анализ правовых интенций
    - Определение сложности запроса
    - Извлечение ключевых терминов
    - Контекстуальный анализ
    - Интеграция с правовой онтологией
    """

    def __init__(self):
        """Инициализация классификатора."""
        self.legal_ontology = get_legal_ontology()
        self.intent_patterns = self._load_intent_patterns()
        self.complexity_indicators = self._load_complexity_indicators()
        self.context_memory = {}
        logger.info(" Smart Query Classifier инициализирован")

    def _load_intent_patterns(self) -> Dict[QueryIntent, List[str]]:
        """Загрузка паттернов для определения интенций."""
        return {
            QueryIntent.FIND_NORM: [
                r"стать[яи]\s+\d+", r"пункт\s+\d+", r"требования?\s+к", r"нормы?\s+для",
                r"что\s+говорит\s+закон", r"где\s+прописано", r"какая\s+статья",
                r"регулирует\s+ли", r"предусмотрено\s+ли", r"есть\s+ли\s+норма"
            ],

            QueryIntent.EXPLAIN_PROCEDURE: [
                r"как\s+получить", r"порядок\s+\w+", r"процедура\s+\w+", r"этапы\s+\w+",
                r"последовательность", r"алгоритм\s+\w+", r"как\s+оформить",
                r"что\s+нужно\s+для", r"документы\s+для", r"как\s+подать"
            ],

            QueryIntent.COMPARE_REQUIREMENTS: [
                r"различи[яе]\s+между", r"чем\s+отличается", r"разница\s+в",
                r"сравни\w*", r"vs\s+", r"или\s+", r"что\s+лучше",
                r"общего\s+между", r"похож\w*\s+на"
            ],

            QueryIntent.FIND_RESPONSIBILITY: [
                r"ответственность\s+за", r"штраф\s+за", r"наказание\s+за",
                r"санкции\s+за", r"что\s+будет\s+если", r"что\s+грозит",
                r"могут\s+ли\s+оштрафовать", r"какие\s+последствия"
            ],

            QueryIntent.GET_DEFINITION: [
                r"что\s+такое", r"определение", r"понятие", r"это\s+\w+",
                r"означает", r"расшифруй\w*", r"объясни\w*\s+простым",
                r"что\s+понимается\s+под"
            ],

            QueryIntent.CALCULATE_PARAMETERS: [
                r"как\s+рассчитать", r"формула\s+для", r"размер\s+\w+",
                r"сколько\s+составляет", r"норматив\s+для", r"параметры\s+\w+",
                r"коэффициент", r"расчет\s+\w+", r"вычислить"
            ],

            QueryIntent.FIND_CONFLICTS: [
                r"противоречи[ят]", r"коллизи[ия]", r"не\s+согласуется",
                r"конфликт\s+норм", r"какая\s+норма\s+главнее",
                r"что\s+применять", r"приоритет\s+имеет"
            ]
        }

    def _load_complexity_indicators(self) -> Dict[QueryComplexity, Dict[str, List[str]]]:
        """Загрузка индикаторов сложности запросов."""
        return {
            QueryComplexity.SIMPLE: {
                "patterns": [
                    r"что\s+такое", r"можно\s+ли", r"разрешено\s+ли",
                    r"запрещено\s+ли", r"да\s+или\s+нет"
                ],
                "indicators": [
                    "простой", "кратко", "в двух словах", "коротко"
                ]
            },

            QueryComplexity.MEDIUM: {
                "patterns": [
                    r"как\s+\w+", r"когда\s+\w+", r"где\s+\w+", r"кто\s+\w+"
                ],
                "indicators": [
                    "процедура", "порядок", "этапы", "алгоритм"
                ]
            },

            QueryComplexity.COMPLEX: {
                "patterns": [
                    r"анализ\s+\w+", r"сравнительный\s+анализ", r"правовая\s+оценка",
                    r"юридические\s+последствия", r"комплексный\s+подход"
                ],
                "indicators": [
                    "детальный", "подробный", "всесторонний", "комплексный",
                    "юридический анализ", "правовая экспертиза"
                ]
            },

            QueryComplexity.EXPERT: {
                "patterns": [
                    r"доктринальн\w+", r"судебная\s+практика", r"толкование\s+норм",
                    r"правоприменительная\s+практика", r"пробелы\s+в\s+праве"
                ],
                "indicators": [
                    "экспертиза", "консультация", "мнение", "позиция",
                    "судебная практика", "прецедент"
                ]
            }
        }

    def analyze_query(self, query: str, conversation_history: Optional[List[Dict]] = None) -> QueryAnalysis:
        """
        Полный анализ запроса.

        Args:
            query: Текст запроса
            conversation_history: История разговора для контекста

        Returns:
            Структурированный анализ запроса
        """
        query_lower = query.lower()

        # 1. Базовая классификация типа
        query_type = self._classify_query_type(query)

        # 2. Определение интенции
        intent = self._detect_intent(query_lower)

        # 3. Анализ сложности
        complexity = self._analyze_complexity(query_lower)

        # 4. Определение правовой отрасли
        legal_domain, domain_confidence = self.legal_ontology.get_legal_domain(query)

        # 5. Извлечение правовых ссылок
        references = self.legal_ontology.extract_legal_references(query)
        extracted_refs = [f"статья {ref.article}" for ref in references if ref.article]

        # 6. Извлечение ключевых терминов
        key_terms = self._extract_key_terms(query_lower)

        # 7. Анализ контекстной зависимости
        has_context_dependency = self._has_context_dependency(query_lower, conversation_history)

        # 8. Определение необходимости расчетов
        requires_calculation = self._requires_calculation(query_lower)

        # 9. Оценка уровня экспертизы пользователя
        user_expertise = self._estimate_user_expertise(query_lower, conversation_history)

        # 10. Общая уверенность в анализе
        confidence = self._calculate_confidence(
            intent, complexity, legal_domain, domain_confidence, key_terms
        )

        return QueryAnalysis(
            query_type=query_type,
            user_expertise=user_expertise,
            complexity=complexity,
            intent=intent,
            legal_area=legal_domain,
            key_concepts=key_terms,
            intent_confidence=confidence
        )

    def analyze_with_context(self, query: str, conversation_history: List[Dict]) -> ContextualQueryAnalysis:
        """
        Анализ запроса с учетом контекста разговора.

        Args:
            query: Текст запроса
            conversation_history: История разговора

        Returns:
            Контекстуальный анализ запроса
        """
        base_analysis = self.analyze_query(query, conversation_history)

        # Анализ контекстных ссылок
        context_references = self._extract_context_references(query, conversation_history)

        # Определение продолжения темы
        continuing_topic = self._is_continuing_topic(query, conversation_history)

        # Определение смены темы
        topic_shift = self._is_topic_shift(query, conversation_history)

        # Необходимость уточнения
        requires_clarification = self._requires_clarification(query, base_analysis)

        # Поиск связанных запросов в истории
        related_queries = self._find_related_queries(query, conversation_history)

        return ContextualQueryAnalysis(
            base_analysis=base_analysis,
            context_references=context_references,
            continuing_topic=continuing_topic,
            topic_shift=topic_shift,
            requires_clarification=requires_clarification,
            related_queries=related_queries
        )

    def _classify_query_type(self, query: str) -> QueryType:
        """Классификация типа запроса (совместимость с существующей системой)."""
        query_lower = query.lower()

        # Проверка на обычное общение
        if self._is_casual_chat(query_lower):
            return QueryType.CASUAL_CHAT

        # Проверка на правовой контент
        is_legal, confidence = self.legal_ontology.is_legal_query(query)
        if not is_legal or confidence < 0.3:
            return QueryType.CASUAL_CHAT

        # Определение конкретного типа правового запроса
        if any(pattern in query_lower for pattern in ["что такое", "определение", "понятие"]):
            return QueryType.SIMPLE_DEFINITION

        if any(pattern in query_lower for pattern in ["как получить", "порядок", "процедура", "этапы"]):
            return QueryType.COMPLEX_PROCEDURE

        if any(pattern in query_lower for pattern in ["сравни", "различия", "отличия", "vs"]):
            return QueryType.COMPARISON

        if any(pattern in query_lower for pattern in ["статья", "закон", "правовое", "ответственность"]):
            return QueryType.LEGAL_ANALYSIS

        if any(pattern in query_lower for pattern in ["сп ", "гост", "снип", "требования к"]):
            return QueryType.REGULATORY_SPECIFIC

        return QueryType.SIMPLE_DEFINITION

    def _detect_intent(self, query_lower: str) -> QueryIntent:
        """Определение интенции запроса."""
        best_intent = QueryIntent.GENERAL_CONSULTATION
        best_score = 0

        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1

            if score > best_score:
                best_score = score
                best_intent = intent

        # Если не нашли специфичную интенцию, но запрос правовой
        if best_score == 0:
            is_legal, _ = self.legal_ontology.is_legal_query(query_lower)
            if is_legal:
                return QueryIntent.GENERAL_CONSULTATION
            else:
                return QueryIntent.CASUAL_CHAT

        return best_intent

    def _analyze_complexity(self, query_lower: str) -> QueryComplexity:
        """Анализ сложности запроса."""
        complexity_scores = {
            complexity: 0 for complexity in QueryComplexity
        }

        for complexity, indicators in self.complexity_indicators.items():
            # Проверка паттернов
            for pattern in indicators.get("patterns", []):
                if re.search(pattern, query_lower):
                    complexity_scores[complexity] += 2

            # Проверка индикаторов
            for indicator in indicators.get("indicators", []):
                if indicator in query_lower:
                    complexity_scores[complexity] += 1

        # Дополнительные критерии сложности
        if len(query_lower.split()) > 20:
            complexity_scores[QueryComplexity.COMPLEX] += 1

        if re.search(r"(стать[яи]\s+\d+.*пункт\s+\d+|подпункт\s+\w+)", query_lower):
            complexity_scores[QueryComplexity.COMPLEX] += 1

        # Возврат наиболее вероятной сложности
        best_complexity = max(complexity_scores.items(), key=lambda x: x[1])
        return best_complexity[0] if best_complexity[1] > 0 else QueryComplexity.SIMPLE

    def _extract_key_terms(self, query_lower: str) -> List[str]:
        """Извлечение ключевых правовых терминов."""
        key_terms = []

        # Правовые термины из онтологии
        for term in self.legal_ontology.LEGAL_SYNONYMS.keys():
            if term in query_lower:
                key_terms.append(term)

        # Аббревиатуры
        for abbr in self.legal_ontology.ABBREVIATIONS.keys():
            if abbr in query_lower:
                key_terms.append(abbr)

        # Номера статей и документов
        article_matches = re.findall(r"стать[яи]\s+(\d+)", query_lower)
        for match in article_matches:
            key_terms.append(f"статья {match}")

        law_matches = re.findall(r"(\d+[-–]\s*фз)", query_lower)
        for match in law_matches:
            key_terms.append(match)

        return list(set(key_terms))

    def _has_context_dependency(self, query_lower: str, conversation_history: Optional[List[Dict]]) -> bool:
        """Определение зависимости от контекста разговора."""
        # Местоимения и указательные слова
        context_indicators = [
            "это", "этот", "эта", "эти", "тот", "та", "те",
            "он", "она", "оно", "они", "его", "её", "их",
            "такой", "такая", "такое", "такие",
            "данный", "данная", "данное", "данные",
            "вышеуказанный", "упомянутый", "рассмотренный"
        ]

        # Неполные фразы
        incomplete_phrases = [
            "а что насчет", "а как с", "а если", "то есть",
            "в таком случае", "в этом случае", "при этом"
        ]

        for indicator in context_indicators + incomplete_phrases:
            if indicator in query_lower:
                return True

        # Короткие запросы часто зависят от контекста
        if len(query_lower.split()) <= 3 and conversation_history:
            return True

        return False

    def _requires_calculation(self, query_lower: str) -> bool:
        """Определение необходимости расчетов."""
        calculation_indicators = [
            "рассчитать", "вычислить", "формула", "размер", "норматив",
            "коэффициент", "параметры", "сколько составляет", "процент"
        ]

        return any(indicator in query_lower for indicator in calculation_indicators)

    def _estimate_user_expertise(self, query_lower: str, conversation_history: Optional[List[Dict]]) -> str:
        """Оценка уровня экспертизы пользователя."""
        expert_indicators = [
            "правоприменительная практика", "судебная практика",
            "доктрина", "толкование", "пробел в праве",
            "коллизия", "системное толкование"
        ]

        intermediate_indicators = [
            "статья", "пункт", "кодекс", "закон", "постановление",
            "ответственность", "процедура", "требования"
        ]

        if any(indicator in query_lower for indicator in expert_indicators):
            return "expert"

        if any(indicator in query_lower for indicator in intermediate_indicators):
            return "intermediate"

        return "beginner"

    def _calculate_confidence(self, intent: QueryIntent, complexity: QueryComplexity,
                            legal_domain: LegalDomain, domain_confidence: float,
                            key_terms: List[str]) -> float:
        """Расчет общей уверенности в анализе."""
        confidence = 0.5 # Базовая уверенность

        # Бонус за найденную интенцию
        if intent != QueryIntent.GENERAL_CONSULTATION:
            confidence += 0.2

        # Бонус за ключевые термины
        confidence += min(len(key_terms) * 0.1, 0.2)

        # Учет уверенности в определении отрасли
        confidence += domain_confidence * 0.1

        return min(confidence, 1.0)

    def _is_casual_chat(self, query_lower: str) -> bool:
        """Определение обычного общения."""
        casual_patterns = [
            r"^(привет|здравствуй|добр\w+\s+(день|утро|вечер))",
            r"(как\s+дела|как\s+поживаешь|что\s+нового)",
            r"(спасибо|благодарю|пока|до\s+свидания)",
            r"(кто\s+ты|как\s+тебя\s+зовут|что\s+ты\s+умеешь)"
        ]

        for pattern in casual_patterns:
            if re.search(pattern, query_lower):
                return True

        # Короткие запросы без правовых терминов
        if len(query_lower.split()) <= 3:
            is_legal, confidence = self.legal_ontology.is_legal_query(query_lower)
            if not is_legal or confidence < 0.2:
                return True

        return False

    def _extract_context_references(self, query: str, conversation_history: List[Dict]) -> List[str]:
        """Извлечение ссылок на контекст из истории."""
        if not conversation_history:
            return []

        context_refs = []
        query_lower = query.lower()

        # Поиск упоминаний из предыдущих сообщений
        for entry in conversation_history[-5:]: # Последние 5 сообщений
            prev_question = entry.get("question", "").lower()
            prev_answer = entry.get("answer", "").lower()

            # Ищем общие ключевые слова
            query_words = set(query_lower.split())
            prev_words = set(prev_question.split() + prev_answer.split())

            common_words = query_words & prev_words
            important_words = [word for word in common_words if len(word) > 3]

            if important_words:
                context_refs.extend(important_words)

        return list(set(context_refs))

    def _is_continuing_topic(self, query: str, conversation_history: List[Dict]) -> bool:
        """Определение продолжения темы разговора."""
        if not conversation_history:
            return False

        last_entry = conversation_history[-1]
        last_domain, _ = self.legal_ontology.get_legal_domain(last_entry.get("question", ""))
        current_domain, _ = self.legal_ontology.get_legal_domain(query)

        return last_domain == current_domain and last_domain != LegalDomain.GENERAL

    def _is_topic_shift(self, query: str, conversation_history: List[Dict]) -> bool:
        """Определение смены темы разговора."""
        if not conversation_history:
            return False

        last_entry = conversation_history[-1]
        last_domain, _ = self.legal_ontology.get_legal_domain(last_entry.get("question", ""))
        current_domain, _ = self.legal_ontology.get_legal_domain(query)

        return (last_domain != current_domain and
                last_domain != LegalDomain.GENERAL and
                current_domain != LegalDomain.GENERAL)

    def _requires_clarification(self, query: str, analysis: QueryAnalysis) -> bool:
        """Определение необходимости уточнения."""
        # Очень короткие запросы
        if len(query.split()) <= 2:
            return True

        # Низкая уверенность в анализе
        if analysis.confidence < 0.4:
            return True

        # Слишком общие запросы
        if not analysis.key_concepts and analysis.intent == QueryIntent.GENERAL_CONSULTATION:
            return True

        return False

    def _find_related_queries(self, query: str, conversation_history: List[Dict]) -> List[str]:
        """Поиск связанных запросов в истории."""
        if not conversation_history:
            return []

        related = []
        current_terms = set(self._extract_key_terms(query.lower()))

        for entry in conversation_history:
            prev_question = entry.get("question", "")
            prev_terms = set(self._extract_key_terms(prev_question.lower()))

            # Если есть общие термины
            if current_terms & prev_terms:
                related.append(prev_question)

        return related[-3:] # Последние 3 связанных запроса


# Глобальный экземпляр классификатора
_smart_classifier = None

def get_smart_classifier() -> SmartQueryClassifier:
    """Получение глобального экземпляра умного классификатора."""
    global _smart_classifier
    if _smart_classifier is None:
        _smart_classifier = SmartQueryClassifier()
    return _smart_classifier


if __name__ == "__main__":
    # Демонстрация возможностей классификатора
    print(" Smart Query Classifier - Демонстрация")
    print("=" * 50)

    classifier = SmartQueryClassifier()

    test_queries = [
        "Статья 51 ГрК РФ о разрешениях на строительство",
        "Привет, как дела?",
        "Как получить разрешение на строительство жилого дома?",
        "Сравните требования 44-ФЗ и 223-ФЗ по закупкам",
        "Что такое теплоснабжение?",
        "А что насчет ответственности за нарушения?",
        "Рассчитайте параметры отопления для здания"
    ]

    for query in test_queries:
        print(f"\n Запрос: {query}")
        analysis = classifier.analyze_query(query)

        print(f" Тип: {analysis.query_type.value}")
        print(f" Интенция: {analysis.intent.value}")
        print(f" Сложность: {analysis.complexity.value}")
        print(f" Отрасль: {analysis.legal_area.value}")
        print(f" Уверенность: {analysis.confidence:.2f}")
        print(f" Уровень пользователя: {analysis.user_expertise_level}")

        if analysis.key_concepts:
            print(f" Ключевые термины: {', '.join(analysis.key_concepts)}")

        if analysis.extracted_references:
            print(f" Ссылки: {', '.join(analysis.extracted_references)}")