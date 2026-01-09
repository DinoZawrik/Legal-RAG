"""Модуль экспорта данных"""

import json
import csv
import io
from typing import List, Dict
from datetime import datetime


class DataExporter:
    """Класс для экспорта данных в различные форматы"""

    @staticmethod
    def export_to_json(data: Dict, filename: str = None) -> str:
        """Экспорт в JSON"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def export_to_csv(data: List[Dict], filename: str = None) -> str:
        """Экспорт в CSV"""
        if not data:
            return ""

        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

        return output.getvalue()

    @staticmethod
    def create_summary_report(user_history: List[Dict], documents: List[Dict]) -> str:
        """Создает сводный отчет"""
        report = []
        report.append("📊 СВОДНЫЙ ОТЧЕТ")
        report.append("=" * 50)
        report.append(f"📅 Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        report.append("")

        report.append("📄 ДОКУМЕНТЫ:")
        for doc in documents[:10]:  # Показываем первые 10
            report.append(f"• {doc.get('filename', 'Неизвестно')}")

        if len(documents) > 10:
            report.append(f"... и еще {len(documents) - 10} документов")

        report.append("")
        report.append("❓ ПОСЛЕДНИЕ ВОПРОСЫ:")
        for question in user_history[:5]:  # Последние 5 вопросов
            report.append(f"• {question.get('question', '')[:100]}...")

        report.append("")
        report.append("📈 СТАТИСТИКА:")
        report.append(f"Всего документов: {len(documents)}")
        report.append(f"Всего вопросов: {len(user_history)}")

        return "\n".join(report)
