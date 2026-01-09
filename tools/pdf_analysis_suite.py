#!/usr/bin/env python3
"""
🔍 PDF Analysis Suite
Объединенный инструмент для анализа PDF файлов и их извлечения.

Включает функциональность из:
- pdf_audit.py
- pdf_extraction_audit.py

Использование:
    python -m tools.pdf_analysis_suite --mode=audit
    python -m tools.pdf_analysis_suite --mode=extraction
    python -m tools.pdf_analysis_suite --mode=full
"""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any
import json
import logging

from core.logging_config import configure_logging

# PDF extraction libraries
try:
    import PyPDF2
    import fitz  # PyMuPDF
    import pdfplumber
except ImportError as e:
    print(f"❌ Необходимые библиотеки не установлены: {e}")
    print("📦 Установите: pip install PyPDF2 PyMuPDF pdfplumber")
    sys.exit(1)

# Core imports
try:
    from core.ai_inference_suite import UnifiedAISystem
    from core.infrastructure_suite import get_settings
    from core.data_storage_suite import UnifiedStorageManager, TextChunk
except ImportError:
    print("❌ Не удается импортировать core модули")
    sys.exit(1)

# Logging setup
configure_logging()
logger = logging.getLogger(__name__)


class PDFAnalysisSuite:
    """Объединенный инструмент для анализа PDF файлов."""
    
    def __init__(self):
        """Инициализация анализатора."""
        self.config = get_settings()
        self.storage_manager = UnifiedStorageManager()
        self.critical_phrases = [
            "схема теплоснабжения",
            "инвестиционная программа",
            "единая теплоснабжающая организация",
            "тарифное регулирование",
            "энергетическая эффективность"
        ]
    
    def find_pdf_files(self) -> List[Path]:
        """Находит все PDF файлы в проекте."""
        pdf_files = []
        search_dirs = ["docs_for_test", "data", "uploads"]
        
        for dir_name in search_dirs:
            dir_path = Path(dir_name)
            if dir_path.exists():
                pdf_files.extend(dir_path.glob("**/*.pdf"))
        
        return pdf_files
    
    def extract_with_pypdf2(self, pdf_path: Path) -> str:
        """Извлечение текста с помощью PyPDF2."""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"PyPDF2 ошибка для {pdf_path}: {e}")
            return ""
    
    def extract_with_pymupdf(self, pdf_path: Path) -> str:
        """Извлечение текста с помощью PyMuPDF (fitz)."""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text += page.get_text() + "\n"
            doc.close()
            return text.strip()
        except Exception as e:
            logger.error(f"PyMuPDF ошибка для {pdf_path}: {e}")
            return ""
    
    def extract_with_pdfplumber(self, pdf_path: Path) -> str:
        """Извлечение текста с помощью pdfplumber."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"pdfplumber ошибка для {pdf_path}: {e}")
            return ""
    
    def test_extraction_methods(self, pdf_path: Path) -> Dict[str, Dict[str, Any]]:
        """Тестирует все методы извлечения для одного файла."""
        results = {}
        
        methods = {
            "pypdf2": self.extract_with_pypdf2,
            "pymupdf": self.extract_with_pymupdf,
            "pdfplumber": self.extract_with_pdfplumber
        }
        
        for method_name, extraction_func in methods.items():
            logger.info(f"🔍 Тестируем {method_name} для {pdf_path.name}")
            
            text = extraction_func(pdf_path)
            
            results[method_name] = {
                "text_length": len(text),
                "lines_count": len(text.split('\n')) if text else 0,
                "phrases_found": self.find_phrases_in_text(text),
                "success": len(text) > 0
            }
        
        return results
    
    def find_phrases_in_text(self, text: str) -> Dict[str, bool]:
        """Ищет критические фразы в тексте."""
        text_lower = text.lower()
        return {
            phrase: phrase.lower() in text_lower 
            for phrase in self.critical_phrases
        }
    
    def analyze_phrases_in_extractions(self, extraction_results: Dict, 
                                     phrases: List[str]) -> Dict[str, Any]:
        """Анализирует наличие фраз в результатах извлечения."""
        analysis = {
            "phrases_analysis": {},
            "method_performance": {},
            "recommendations": []
        }
        
        for phrase in phrases:
            phrase_results = {}
            for method, result in extraction_results.items():
                found = result.get("phrases_found", {}).get(phrase, False)
                phrase_results[method] = found
            
            analysis["phrases_analysis"][phrase] = phrase_results
            
            # Рекомендации по методу
            found_in_methods = [m for m, found in phrase_results.items() if found]
            if found_in_methods:
                analysis["recommendations"].append(
                    f"✅ '{phrase}' найдена в: {', '.join(found_in_methods)}"
                )
            else:
                analysis["recommendations"].append(
                    f"❌ '{phrase}' не найдена ни в одном методе"
                )
        
        # Анализ производительности методов
        for method, result in extraction_results.items():
            found_count = sum(1 for found in result.get("phrases_found", {}).values() if found)
            total_phrases = len(phrases)
            
            analysis["method_performance"][method] = {
                "phrases_found": found_count,
                "success_rate": (found_count / total_phrases) * 100,
                "text_length": result.get("text_length", 0)
            }
        
        return analysis
    
    async def audit_pdf_files(self) -> Dict[str, Any]:
        """Проводит аудит всех PDF файлов."""
        logger.info("🔍 Начинаем аудит PDF файлов...")
        
        pdf_files = self.find_pdf_files()
        if not pdf_files:
            return {"error": "PDF файлы не найдены"}
        
        audit_results = {
            "total_files": len(pdf_files),
            "file_results": {},
            "summary": {
                "successful_extractions": 0,
                "failed_extractions": 0,
                "best_method": None
            }
        }
        
        method_scores = {"pypdf2": 0, "pymupdf": 0, "pdfplumber": 0}
        
        for pdf_path in pdf_files:
            logger.info(f"📄 Анализируем: {pdf_path.name}")
            
            extraction_results = self.test_extraction_methods(pdf_path)
            phrase_analysis = self.analyze_phrases_in_extractions(
                extraction_results, self.critical_phrases
            )
            
            audit_results["file_results"][str(pdf_path)] = {
                "extraction_results": extraction_results,
                "phrase_analysis": phrase_analysis
            }
            
            # Подсчет очков для методов
            for method, performance in phrase_analysis["method_performance"].items():
                method_scores[method] += performance["success_rate"]
            
            # Статистика успешности
            if any(r["success"] for r in extraction_results.values()):
                audit_results["summary"]["successful_extractions"] += 1
            else:
                audit_results["summary"]["failed_extractions"] += 1
        
        # Определение лучшего метода
        best_method = max(method_scores.items(), key=lambda x: x[1])
        audit_results["summary"]["best_method"] = {
            "name": best_method[0],
            "score": best_method[1] / len(pdf_files)
        }
        
        return audit_results
    
    async def compare_with_database(self, pdf_path: Path, qa_service: UnifiedAISystem) -> Dict:
        """Сравнивает извлеченный текст с базой данных."""
        extraction_results = self.test_extraction_methods(pdf_path)
        
        comparison_results = {
            "file": str(pdf_path),
            "database_comparison": {},
            "recommendations": []
        }
        
        for method, result in extraction_results.items():
            if not result["success"]:
                continue
            
            # Поиск фраз в базе данных
            phrases_in_db = {}
            for phrase in self.critical_phrases:
                try:
                    # Используем UnifiedStorageManager для поиска
                    search_result = await self.storage_manager.search_documents(phrase, limit=1)
                    phrases_in_db[phrase] = len(search_result) > 0
                except Exception as e:
                    logger.error(f"Ошибка поиска '{phrase}' в БД: {e}")
                    phrases_in_db[phrase] = False
            
            comparison_results["database_comparison"][method] = {
                "phrases_in_extraction": result.get("phrases_found", {}),
                "phrases_in_database": phrases_in_db
            }
        
        return comparison_results
    
    async def run_full_analysis(self) -> Dict[str, Any]:
        """Запускает полный анализ PDF файлов."""
        logger.info("🚀 Запуск полного анализа PDF...")
        
        # Аудит файлов
        audit_results = await self.audit_pdf_files()
        
        # Сравнение с базой данных (если доступна)
        try:
            await self.storage_manager.initialize()
            qa_service = UnifiedAISystem()
            pdf_files = self.find_pdf_files()
            
            database_comparisons = []
            for pdf_path in pdf_files[:3]:  # Ограничиваем для скорости
                comparison = await self.compare_with_database(pdf_path, qa_service)
                database_comparisons.append(comparison)
            
            audit_results["database_comparisons"] = database_comparisons
        except Exception as e:
            logger.warning(f"Пропуск сравнения с БД: {e}")
            audit_results["database_comparisons"] = "Недоступно"
        finally:
            await self.storage_manager.close_all()

        return audit_results
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "pdf_analysis_report.json"):
        """Генерирует отчет по анализу."""
        logger.info(f"📊 Сохраняем отчет в {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Краткий отчет в консоль
        print("\n" + "="*60)
        print("📊 ОТЧЕТ ПО АНАЛИЗУ PDF ФАЙЛОВ")
        print("="*60)
        
        if "total_files" in results:
            print(f"📄 Всего файлов: {results['total_files']}")
            summary = results.get("summary", {})
            print(f"✅ Успешные извлечения: {summary.get('successful_extractions', 0)}")
            print(f"❌ Неудачные извлечения: {summary.get('failed_extractions', 0)}")
            
            best_method = summary.get("best_method")
            if best_method:
                print(f"🏆 Лучший метод: {best_method['name']} (очки: {best_method['score']:.1f})")
        
        print(f"💾 Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="PDF Analysis Suite")
    parser.add_argument(
        "--mode", 
        choices=["audit", "extraction", "full"], 
        default="full",
        help="Режим анализа"
    )
    parser.add_argument(
        "--output", 
        default="pdf_analysis_report.json",
        help="Файл для отчета"
    )
    
    args = parser.parse_args()
    
    suite = PDFAnalysisSuite()
    
    try:
        if args.mode == "audit":
            results = await suite.audit_pdf_files()
        elif args.mode == "extraction":
            # Для extraction запускаем только первый файл
            pdf_files = suite.find_pdf_files()
            if pdf_files:
                results = suite.test_extraction_methods(pdf_files[0])
            else:
                results = {"error": "PDF файлы не найдены"}
        else:  # full
            results = await suite.run_full_analysis()
        
        suite.generate_report(results, args.output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
