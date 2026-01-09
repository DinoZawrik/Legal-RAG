"""Regex pattern providers for legal structure detection."""

from typing import Dict, List

from .definitions import StructureLevel


def load_structure_patterns() -> Dict[StructureLevel, List[str]]:
    """Return regex groups describing hierarchical document markers."""

    return {
        StructureLevel.CHAPTER: [
            r"^Глава\s+([IVXLC]+|\d+)\.?\s*(.+)$",
            r"^ГЛАВА\s+([IVXLC]+|\d+)\.?\s*(.+)$",
            r"^Раздел\s+([IVXLC]+|\d+)\.?\s*(.+)$",
        ],
        StructureLevel.SECTION: [
            r"^§\s*(\d+)\.?\s*(.+)$",
            r"^Параграф\s+(\d+)\.?\s*(.+)$",
            r"^Подраздел\s+(\d+)\.?\s*(.+)$",
        ],
        StructureLevel.ARTICLE: [
            r"^Статья\s+(\d+(?:\.\d+)*)\.?\s*(.*)$",
            r"^Ст\.\s*(\d+(?:\.\d+)*)\.?\s*(.*)$",
            r"^(\d+(?:\.\d+)*)\.?\s+(.+)$",
        ],
        StructureLevel.PARAGRAPH: [
            r"^(\d+)\.?\s+(.+)$",
            r"^(\d+)\)\s+(.+)$",
            r"^\((\d+)\)\s+(.+)$",
        ],
        StructureLevel.SUBPARAGRAPH: [
            r"^([а-я])\)\s+(.+)$",
            r"^\(([а-я])\)\s+(.+)$",
            r"^([а-я])\.?\s+(.+)$",
        ],
        StructureLevel.ITEM: [
            r"^-\s+(.+)$",
            r"^\*\s+(.+)$",
            r"^•\s+(.+)$",
            r"^(\w+)\s*:\s*(.+)$",
        ],
    }


def load_critical_numerical_patterns() -> List[str]:
    """Return patterns highlighting critical numeric constraints in legal text."""

    return [
        r"(?:размер|сумма|объем).{0,50}(?:не\s+)?может\s+превышать\s+восемьдесят\s+процент[а-я]*",
        r"(?:размер|сумма|объем).{0,50}(?:не\s+)?может\s+превышать\s+80\s*%",
        r"капитальный\s+грант.{0,50}не\s+может\s+превышать\s+восемьдесят\s+процент[а-я]*",
        r"капитальный\s+грант.{0,50}не\s+может\s+превышать\s+80\s*%",
        r"срок.{0,50}не\s+менее\s+(?:чем\s+)?три\s+года",
        r"срок.{0,50}не\s+менее\s+(?:чем\s+)?3\s+лет",
        r"минимальный\s+срок.{0,30}три\s+года",
        r"предельный\s+размер.{0,100}финансового?\s+участия",
        r"максимальный\s+размер.{0,100}(?:гранта|участия|финансирования)",
        r"ограничение.{0,50}процент[а-я]*",
        r"статья\s+10\.1.{0,200}восемьдесят\s+процент[а-я]*",
        r"статья\s+12\.1.{0,200}восемьдесят\s+процент[а-я]*",
        r"статья\s+3.{0,200}не\s+менее.{0,50}три\s+года",
    ]
