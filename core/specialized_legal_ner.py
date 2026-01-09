"""
Specialized Legal NER for Numerical Data Extraction
Решает проблему потери численных ограничений: 80%, "не менее 3 лет", сумм
Универсальная система для любых российских правовых документов
"""

import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class NumericalConstraintType(Enum):
    """Типы численных ограничений в правовых документах"""
    PERCENTAGE = "percentage"  # 80%, пятьдесят процентов
    MONETARY = "monetary"      # 1000000 рублей, миллион рублей
    TEMPORAL = "temporal"      # 3 года, не менее трех лет
    QUANTITY = "quantity"      # не более 50 участников
    RATIO = "ratio"           # в размере 1/3, одна треть
    THRESHOLD = "threshold"    # свыше 100 миллионов


class ModalityType(Enum):
    """Модальности в правовых текстах"""
    MANDATORY = "mandatory"    # должен, обязан
    PROHIBITED = "prohibited"  # не может, запрещается
    PERMITTED = "permitted"    # может, имеет право
    CONDITIONAL = "conditional" # при условии, если


@dataclass
class NumericalEntity:
    """Численная сущность с контекстом"""
    value: str
    normalized_value: float
    constraint_type: NumericalConstraintType
    modality: ModalityType
    context: str
    article_ref: Optional[str] = None
    part_ref: Optional[str] = None
    law_ref: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'value': self.value,
            'normalized_value': self.normalized_value,
            'constraint_type': self.constraint_type.value,
            'modality': self.modality.value,
            'context': self.context,
            'article_ref': self.article_ref,
            'part_ref': self.part_ref,
            'law_ref': self.law_ref,
            'confidence': self.confidence
        }


@dataclass
class LegalEntityCollection:
    """Коллекция правовых сущностей из документа"""
    numerical_entities: List[NumericalEntity] = field(default_factory=list)
    article_references: List[Dict[str, Any]] = field(default_factory=list)
    law_references: List[Dict[str, Any]] = field(default_factory=list)
    legal_concepts: List[Dict[str, Any]] = field(default_factory=list)

    def add_numerical_entity(self, entity: NumericalEntity):
        """Добавить численную сущность"""
        self.numerical_entities.append(entity)

    def get_entities_by_type(self, constraint_type: NumericalConstraintType) -> List[NumericalEntity]:
        """Получить сущности по типу ограничения"""
        return [e for e in self.numerical_entities if e.constraint_type == constraint_type]

    def get_all_entities(self) -> List[Dict[str, Any]]:
        """Получить все сущности в формате словаря"""
        result = []
        for entity in self.numerical_entities:
            result.append(entity.to_dict())
        for ref in self.article_references:
            result.append({'type': 'article_reference', **ref})
        for ref in self.law_references:
            result.append({'type': 'law_reference', **ref})
        for concept in self.legal_concepts:
            result.append({'type': 'legal_concept', **concept})
        return result


class SpecializedLegalNER:
    """
    Специализированный NER для извлечения численных данных из правовых документов
    Решает проблему 32.5% ошибок связанных с потерей численных ограничений
    """

    def __init__(self):
        self.percentage_patterns = self._compile_percentage_patterns()
        self.monetary_patterns = self._compile_monetary_patterns()
        self.temporal_patterns = self._compile_temporal_patterns()
        self.quantity_patterns = self._compile_quantity_patterns()
        self.modality_patterns = self._compile_modality_patterns()
        self.article_patterns = self._compile_article_patterns()
        self.law_patterns = self._compile_law_patterns()

        # Русские числительные для нормализации
        self.russian_numbers = self._load_russian_numbers()

    def _compile_percentage_patterns(self) -> List[re.Pattern]:
        """Паттерны для процентов"""
        patterns = [
            # Цифровые проценты: 80%, 50,5%
            r'(\d+(?:[,\.]\d+)?)\s*(?:процент[а-я]*|%)',

            # Текстовые проценты: восемьдесят процентов
            r'((?:один|два|три|четыре|пять|шесть|семь|восемь|девять|десять|'
            r'одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|'
            r'шестнадцать|семнадцать|восемнадцать|девятнадцать|двадцать|'
            r'тридцать|сорок|пятьдесят|шестьдесят|семьдесят|восемьдесят|'
            r'девяносто|сто)\s+процент[а-я]*)',

            # Дробные проценты: одна вторая, две третьих
            r'((?:одна|две|три|четыре|пять)\s+(?:вторая|третья|четвертая|пятая|шестая)[х]?)',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_monetary_patterns(self) -> List[re.Pattern]:
        """Паттерны для денежных сумм"""
        patterns = [
            # Цифровые суммы: 1000000 рублей, 1 млн руб
            r'(\d+(?:\s?\d{3})*(?:[,\.]\d+)?)\s*(?:рубл[ей]*|руб\.?|тыс\.?|млн\.?|млрд\.?)',

            # Текстовые суммы: миллион рублей, тысяча рублей
            r'((?:тысяча|миллион|миллиард|триллион)[а-я]*)\s*рубл[ей]*',

            # МРОТ, прожиточный минимум
            r'(\d+(?:[,\.]\d+)?)\s*(?:МРОТ|прожиточн[а-я]*\s*минимум[а-я]*)',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_temporal_patterns(self) -> List[re.Pattern]:
        """Паттерны для временных ограничений"""
        patterns = [
            # Годы: 3 года, не менее трех лет
            r'(?:не\s+)?(?:менее|более|свыше)?\s*(\d+|(?:одного|двух|трех|четырех|пяти|шести|семи|восьми|девяти|десяти))\s*(?:год[а-я]*|лет[а]?)',

            # Месяцы: 6 месяцев, полгода
            r'(?:не\s+)?(?:менее|более|свыше)?\s*(\d+|(?:одного|двух|трех|четырех|пяти|шести|семи|восьми|девяти|десяти|полу?))\s*месяц[а-я]*',

            # Дни: 30 дней, тридцать календарных дней
            r'(?:не\s+)?(?:менее|более|свыше)?\s*(\d+|(?:один|два|три|четыре|пять|десять|двадцать|тридцать))\s*(?:календарн[а-я]*\s*)?дн[ей]*',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_quantity_patterns(self) -> List[re.Pattern]:
        """Паттерны для количественных ограничений"""
        patterns = [
            # Участники: не более 50 участников
            r'(?:не\s+)?(?:менее|более|свыше)?\s*(\d+)\s*участник[а-я]*',

            # Доли: доля не менее 25%
            r'доля\s*(?:не\s+)?(?:менее|более|свыше)?\s*(\d+(?:[,\.]\d+)?)\s*(?:процент[а-я]*|%)',

            # Размеры: размер не превышает
            r'размер\s*(?:не\s+)?(?:превышает|менее|более|свыше)?\s*(\d+(?:\s?\d{3})*(?:[,\.]\d+)?)',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_modality_patterns(self) -> Dict[ModalityType, List[re.Pattern]]:
        """Паттерны для модальностей"""
        patterns = {
            ModalityType.MANDATORY: [
                r'(?:должен|обязан|необходимо|требуется|подлежит)',
                r'(?:в обязательном порядке|обязательно)',
            ],
            ModalityType.PROHIBITED: [
                r'(?:не может|не имеет права|запрещается|не допускается)',
                r'(?:недопустимо|исключается)',
            ],
            ModalityType.PERMITTED: [
                r'(?:может|имеет право|вправе|допускается)',
                r'(?:разрешается|позволяется)',
            ],
            ModalityType.CONDITIONAL: [
                r'(?:при условии|если|в случае|при наличии)',
                r'(?:при соблюдении|при выполнении)',
            ]
        }

        compiled = {}
        for modality, pattern_list in patterns.items():
            compiled[modality] = [re.compile(p, re.IGNORECASE) for p in pattern_list]
        return compiled

    def _compile_article_patterns(self) -> List[re.Pattern]:
        """Паттерны для ссылок на статьи"""
        patterns = [
            # Статья 7, ст. 15
            r'(?:статья|статьи|ст\.?)\s*(\d+(?:\.\d+)?)',

            # Часть 2 статьи 10
            r'(?:часть|части|ч\.?)\s*(\d+)\s*(?:статьи|ст\.?)\s*(\d+)',

            # Пункт 3 части 1 статьи 5
            r'(?:пункт[а-я]*|п\.?)\s*(\d+)\s*(?:части|ч\.?)\s*(\d+)\s*(?:статьи|ст\.?)\s*(\d+)',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_law_patterns(self) -> List[re.Pattern]:
        """Паттерны для ссылок на законы"""
        patterns = [
            # 115-ФЗ, 224-ФЗ
            r'(\d+)-ФЗ',

            # Федеральный закон от ... № 115-ФЗ
            r'(?:Федеральный закон|ФЗ).*?№\s*(\d+)-ФЗ',

            # Закон № 115-ФЗ "О концессионных соглашениях"
            r'(?:Закон|ФЗ)\s*№?\s*(\d+)-ФЗ\s*["\«]([^"»]+)["\»]',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _load_russian_numbers(self) -> Dict[str, int]:
        """Словарь русских числительных"""
        return {
            'один': 1, 'одного': 1, 'одной': 1, 'одну': 1,
            'два': 2, 'двух': 2, 'две': 2,
            'три': 3, 'трех': 3, 'трём': 3,
            'четыре': 4, 'четырех': 4, 'четырём': 4,
            'пять': 5, 'пяти': 5,
            'шесть': 6, 'шести': 6,
            'семь': 7, 'семи': 7,
            'восемь': 8, 'восьми': 8,
            'девять': 9, 'девяти': 9,
            'десять': 10, 'десяти': 10,
            'одиннадцать': 11, 'двенадцать': 12, 'тринадцать': 13,
            'четырнадцать': 14, 'пятнадцать': 15, 'шестнадцать': 16,
            'семнадцать': 17, 'восемнадцать': 18, 'девятнадцать': 19,
            'двадцать': 20, 'тридцать': 30, 'сорок': 40, 'пятьдесят': 50,
            'шестьдесят': 60, 'семьдесят': 70, 'восемьдесят': 80, 'девяносто': 90,
            'сто': 100, 'тысяча': 1000, 'миллион': 1000000, 'миллиард': 1000000000
        }

    def extract_entities(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> LegalEntityCollection:
        """
        Основной метод извлечения численных сущностей

        Args:
            text: Текст документа
            document_metadata: Метаданные документа (номер закона и т.д.)

        Returns:
            LegalEntityCollection: Коллекция извлеченных сущностей
        """
        collection = LegalEntityCollection()

        # Извлекаем численные сущности по типам
        collection.numerical_entities.extend(self._extract_percentages(text))
        collection.numerical_entities.extend(self._extract_monetary(text))
        collection.numerical_entities.extend(self._extract_temporal(text))
        collection.numerical_entities.extend(self._extract_quantities(text))

        # Извлекаем ссылки
        collection.article_references = self._extract_article_references(text)
        collection.law_references = self._extract_law_references(text)

        # Извлекаем правовые концепции
        collection.legal_concepts = self._extract_legal_concepts(text)

        # Обогащаем сущности контекстом и модальностями
        self._enrich_with_context(collection, text)

        return collection

    def _extract_percentages(self, text: str) -> List[NumericalEntity]:
        """Извлечение процентов"""
        entities = []

        for pattern in self.percentage_patterns:
            for match in pattern.finditer(text):
                value_str = match.group(1)
                context = self._get_context(text, match.start(), match.end())

                # Нормализация значения
                normalized_value = self._normalize_percentage(value_str)

                # Определение модальности
                modality = self._detect_modality(context)

                entity = NumericalEntity(
                    value=value_str,
                    normalized_value=normalized_value,
                    constraint_type=NumericalConstraintType.PERCENTAGE,
                    modality=modality,
                    context=context
                )

                entities.append(entity)

        return entities

    def _extract_monetary(self, text: str) -> List[NumericalEntity]:
        """Извлечение денежных сумм"""
        entities = []

        for pattern in self.monetary_patterns:
            for match in pattern.finditer(text):
                value_str = match.group(1)
                context = self._get_context(text, match.start(), match.end())

                # Нормализация значения в рубли
                normalized_value = self._normalize_monetary(value_str, match.group(0))

                modality = self._detect_modality(context)

                entity = NumericalEntity(
                    value=value_str,
                    normalized_value=normalized_value,
                    constraint_type=NumericalConstraintType.MONETARY,
                    modality=modality,
                    context=context
                )

                entities.append(entity)

        return entities

    def _extract_temporal(self, text: str) -> List[NumericalEntity]:
        """Извлечение временных ограничений"""
        entities = []

        for pattern in self.temporal_patterns:
            for match in pattern.finditer(text):
                value_str = match.group(1)
                context = self._get_context(text, match.start(), match.end())

                # Нормализация в дни
                normalized_value = self._normalize_temporal(value_str, match.group(0))

                modality = self._detect_modality(context)

                entity = NumericalEntity(
                    value=value_str,
                    normalized_value=normalized_value,
                    constraint_type=NumericalConstraintType.TEMPORAL,
                    modality=modality,
                    context=context
                )

                entities.append(entity)

        return entities

    def _extract_quantities(self, text: str) -> List[NumericalEntity]:
        """Извлечение количественных ограничений"""
        entities = []

        for pattern in self.quantity_patterns:
            for match in pattern.finditer(text):
                value_str = match.group(1)
                context = self._get_context(text, match.start(), match.end())

                normalized_value = float(value_str.replace(',', '.'))
                modality = self._detect_modality(context)

                entity = NumericalEntity(
                    value=value_str,
                    normalized_value=normalized_value,
                    constraint_type=NumericalConstraintType.QUANTITY,
                    modality=modality,
                    context=context
                )

                entities.append(entity)

        return entities

    def _extract_article_references(self, text: str) -> List[Dict[str, Any]]:
        """Извлечение ссылок на статьи"""
        references = []

        for pattern in self.article_patterns:
            for match in pattern.finditer(text):
                context = self._get_context(text, match.start(), match.end())

                if len(match.groups()) == 1:
                    # Простая ссылка: статья 7
                    ref = {
                        'article': match.group(1),
                        'context': context,
                        'type': 'simple_article'
                    }
                elif len(match.groups()) == 2:
                    # Часть статьи: часть 2 статьи 10
                    ref = {
                        'article': match.group(2),
                        'part': match.group(1),
                        'context': context,
                        'type': 'article_part'
                    }
                elif len(match.groups()) == 3:
                    # Пункт части статьи: пункт 3 части 1 статьи 5
                    ref = {
                        'article': match.group(3),
                        'part': match.group(2),
                        'point': match.group(1),
                        'context': context,
                        'type': 'article_part_point'
                    }

                references.append(ref)

        return references

    def _extract_law_references(self, text: str) -> List[Dict[str, Any]]:
        """Извлечение ссылок на законы"""
        references = []

        for pattern in self.law_patterns:
            for match in pattern.finditer(text):
                context = self._get_context(text, match.start(), match.end())

                ref = {
                    'law_number': match.group(1),
                    'context': context,
                    'type': 'federal_law'
                }

                # Если есть название закона
                if len(match.groups()) > 1:
                    ref['law_title'] = match.group(2)

                references.append(ref)

        return references

    def _extract_legal_concepts(self, text: str) -> List[Dict[str, Any]]:
        """Извлечение правовых концепций"""
        concepts = []

        # Ключевые правовые термины
        legal_terms = [
            'концессионное соглашение', 'концедент', 'концессионер',
            'плата концедента', 'государственная регистрация',
            'федеральный закон', 'подзаконный акт',
            'административная ответственность', 'гражданская ответственность',
            'договор', 'соглашение', 'обязательство'
        ]

        for term in legal_terms:
            pattern = re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                context = self._get_context(text, match.start(), match.end())

                concept = {
                    'term': term,
                    'context': context,
                    'type': 'legal_concept'
                }

                concepts.append(concept)

        return concepts

    def _get_context(self, text: str, start: int, end: int, window: int = 100) -> str:
        """Получить контекст вокруг найденного совпадения"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()

    def _detect_modality(self, context: str) -> ModalityType:
        """Определить модальность по контексту"""
        for modality, patterns in self.modality_patterns.items():
            for pattern in patterns:
                if pattern.search(context):
                    return modality

        return ModalityType.MANDATORY  # По умолчанию

    def _normalize_percentage(self, value_str: str) -> float:
        """Нормализация процентов"""
        # Если это число
        if value_str.replace(',', '.').replace(' ', '').isdigit() or '.' in value_str:
            return float(value_str.replace(',', '.').replace(' ', ''))

        # Если это текстовое число
        words = value_str.lower().split()
        for word in words:
            if word in self.russian_numbers:
                return float(self.russian_numbers[word])

        return 0.0

    def _normalize_monetary(self, value_str: str, full_match: str) -> float:
        """Нормализация денежных сумм в рубли"""
        # Убираем пробелы и заменяем запятые на точки
        clean_value = value_str.replace(' ', '').replace(',', '.')

        # Если это текстовое число
        if not clean_value.replace('.', '').isdigit():
            for word, number in self.russian_numbers.items():
                if word in value_str.lower():
                    clean_value = str(number)
                    break

        try:
            base_value = float(clean_value)
        except ValueError:
            return 0.0

        # Применяем множители
        full_match_lower = full_match.lower()
        if 'млрд' in full_match_lower or 'миллиард' in full_match_lower:
            return base_value * 1000000000
        elif 'млн' in full_match_lower or 'миллион' in full_match_lower:
            return base_value * 1000000
        elif 'тыс' in full_match_lower or 'тысяча' in full_match_lower:
            return base_value * 1000

        return base_value

    def _normalize_temporal(self, value_str: str, full_match: str) -> float:
        """Нормализация временных ограничений в дни"""
        # Нормализуем число
        if value_str.replace(',', '.').isdigit():
            base_value = float(value_str.replace(',', '.'))
        else:
            base_value = self.russian_numbers.get(value_str.lower(), 0)

        # Определяем единицу времени
        full_match_lower = full_match.lower()
        if 'год' in full_match_lower or 'лет' in full_match_lower:
            return base_value * 365
        elif 'месяц' in full_match_lower:
            return base_value * 30
        elif 'день' in full_match_lower or 'дн' in full_match_lower:
            return base_value

        return base_value

    def _enrich_with_context(self, collection: LegalEntityCollection, text: str):
        """Обогащение сущностей дополнительным контекстом"""
        # Найдем все ссылки на статьи и законы для связывания
        article_refs = {ref['article']: ref for ref in collection.article_references}
        law_refs = {ref['law_number']: ref for ref in collection.law_references}

        # Обогащаем численные сущности ссылками
        for entity in collection.numerical_entities:
            # Ищем ближайшую ссылку на статью
            entity_context = entity.context.lower()

            for article_num, ref in article_refs.items():
                if f"статья {article_num}" in entity_context or f"ст. {article_num}" in entity_context:
                    entity.article_ref = article_num
                    if 'part' in ref:
                        entity.part_ref = ref['part']
                    break

            # Ищем ссылку на закон
            for law_num, ref in law_refs.items():
                if f"{law_num}-фз" in entity_context:
                    entity.law_ref = law_num
                    break


def create_specialized_ner() -> SpecializedLegalNER:
    """Фабричная функция для создания специализированного NER"""
    return SpecializedLegalNER()


# Пример использования
if __name__ == "__main__":
    ner = create_specialized_ner()

    # Тестовый текст с численными ограничениями
    test_text = """
    Статья 7. Плата концедента

    1. Концедент имеет право на получение платы за предоставление прав по концессионному
    соглашению (плата концедента) в размере, который не может быть более восьмидесяти
    процентов валовой выручки концессионера за определенный период.

    2. Размер платы концедента не может превышать 1000000 рублей в год при условии
    соблюдения требований статьи 15 Федерального закона № 115-ФЗ.

    3. Срок действия концессионного соглашения не может быть менее трех лет.
    """

    entities = ner.extract_entities(test_text)

    print(f"Найдено сущностей: {len(entities.get_all_entities())}")
    for entity in entities.get_all_entities():
        print(f"- {entity}")