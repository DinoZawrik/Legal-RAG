#!/usr/bin/env python3
"""
🔍 Search & Content Diagnostics Suite
Объединенный инструмент для диагностики поиска и анализа контента.

Включает функциональность из:
- search_diagnostics.py  
- advanced_search_diagnostics.py
- quick_content_audit.py

Использование:
    python -m tools.search_diagnostics_suite --mode=basic
    python -m tools.search_diagnostics_suite --mode=advanced  
    python -m tools.search_diagnostics_suite --mode=content
    python -m tools.search_diagnostics_suite --mode=full
"""

import sys
import asyncio
import argparse
import json
import logging
import re
from pathlib import Path

# Core imports
try:
    from core.infrastructure_suite import get_settings
    from core.storage_coordinator import create_storage_coordinator, StorageCoordinator
    from core.logging_config import configure_logging
except ImportError:
    print("❌ Не удается импортировать core модули")
    sys.exit(1)

# Logging setup
configure_logging()
logger = logging.getLogger(__name__)


class SearchDiagnosticsSuite:
    """Объединенный инструмент для диагностики поиска и контента."""
    
    def __init__(self):
        """Инициализация диагностического набора."""
        self.config = get_settings()
        self.storage_manager: UnifiedStorageManager | None = None
        
        # Критические фразы для тестирования
        self.critical_phrases = [
            "схема теплоснабжения",
            "инвестиционная программа", 
            "единая теплоснабжающая организация",
            "тарифное регулирование",
            "энергетическая эффективность",
            "органы местного самоуправления",
            "федеральная антимонопольная служба",
            "региональная энергетическая комиссия"
        ]
        
        # Тестовые вопросы
        self.test_questions = [
            "Что такое схема теплоснабжения?",
            "Кто утверждает инвестиционные программы?",
            "Какие полномочия у органов местного самоуправления?",
            "Как осуществляется тарифное регулирование?"
        ]
    
    async def initialize_storage_manager(self):
        """Инициализирует менеджер хранилища."""
        try:
            self.storage_manager = await create_storage_coordinator()
            logger.info("✅ Менеджер хранилища инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера хранилища: {e}")
            raise
    
    # === БАЗОВАЯ ДИАГНОСТИКА ===
    
    async def find_document_content(self, search_text: str) -> List[Dict[str, Any]]:
        """Поиск конкретного контента в документах."""
        if not self.storage_manager:
            await self.initialize_storage_manager()
        
        logger.info(f"🔍 Поиск контента: {search_text}")
        
        try:
            search_result = await self.storage_manager.search_documents(search_text, limit=5)
            
            found_documents = []
            for doc in search_result:
                content = doc.get("text", "")
                
                # Поиск контекста вокруг найденного текста
                context = self.extract_context_around_phrase(content, search_text)
                
                found_documents.append({
                    "document_id": doc.get("id", "unknown"),
                    "relevance_score": doc.get("similarity", 0.0),
                    "context": context,
                    "metadata": doc.get("metadata", {})
                })
            
            return found_documents
            
        except Exception as e:
            logger.error(f"Ошибка поиска контента '{search_text}': {e}")
            return []
    
    def extract_context_around_phrase(self, content: str, phrase: str, 
                                    context_length: int = 200) -> str:
        """Извлекает контекст вокруг найденной фразы."""
        content_lower = content.lower()
        phrase_lower = phrase.lower()
        
        index = content_lower.find(phrase_lower)
        if index == -1:
            return "Фраза не найдена в тексте"
        
        start = max(0, index - context_length)
        end = min(len(content), index + len(phrase) + context_length)
        
        context = content[start:end]
        return f"...{context}..." if start > 0 or end < len(content) else context
    
    # === ПРОДВИНУТАЯ ДИАГНОСТИКА ===
    
    async def comprehensive_search_analysis(self) -> Dict[str, Any]:
        """Комплексный анализ поисковых возможностей."""
        logger.info("🚀 Запуск комплексного анализа поиска...")
        
        analysis = {
            "document_coverage": await self.analyze_document_coverage(),
            "missing_content": await self.analyze_missing_critical_content(),
            "search_performance": await self.test_search_approaches(),
            "recommendations": []
        }
        
        # Генерация рекомендаций
        analysis["recommendations"] = self.generate_improvement_recommendations(
            analysis["document_coverage"],
            analysis["missing_content"]
        )
        
        return analysis
    
    async def analyze_document_coverage(self) -> Dict[str, Any]:
        """Анализирует покрытие документов."""
        if not self.storage_manager:
            await self.initialize_storage_manager()
        
        coverage_analysis = {
            "total_phrases_tested": len(self.critical_phrases),
            "phrase_coverage": {},
            "coverage_statistics": {
                "found_phrases": 0,
                "missing_phrases": 0,
                "coverage_percentage": 0.0
            }
        }
        
        for phrase in self.critical_phrases:
            logger.info(f"📊 Анализируем покрытие: {phrase}")
            
            try:
                # Прямой поиск
                direct_search = await self.storage_manager.search_documents(phrase, limit=3)
                
                # Поиск вариаций
                variations = self.generate_phrase_variations(phrase)
                variation_results = []
                
                for variation in variations:
                    var_result = await self.storage_manager.search_documents(variation, limit=1)
                    if var_result:
                        variation_results.append({
                            "variation": variation,
                            "found": True,
                            "relevance": var_result.get("similarity", 0.0)
                        })
                
                coverage_analysis["phrase_coverage"][phrase] = {
                    "direct_search_results": len(direct_search),
                    "variations_found": len(variation_results),
                    "total_variations_tested": len(variations),
                    "variation_results": variation_results,
                    "found": len(direct_search) > 0 or len(variation_results) > 0
                }
                
                if coverage_analysis["phrase_coverage"][phrase]["found"]:
                    coverage_analysis["coverage_statistics"]["found_phrases"] += 1
                else:
                    coverage_analysis["coverage_statistics"]["missing_phrases"] += 1
                    
            except Exception as e:
                logger.error(f"Ошибка анализа покрытия '{phrase}': {e}")
                coverage_analysis["phrase_coverage"][phrase] = {"error": str(e)}
        
        # Рассчитываем процент покрытия
        total = coverage_analysis["coverage_statistics"]["found_phrases"] + \
                coverage_analysis["coverage_statistics"]["missing_phrases"]
        
        if total > 0:
            coverage_analysis["coverage_statistics"]["coverage_percentage"] = \
                (coverage_analysis["coverage_statistics"]["found_phrases"] / total) * 100
        
        return coverage_analysis
    
    def generate_phrase_variations(self, phrase: str) -> List[str]:
        """Генерирует вариации фразы для поиска."""
        variations = []
        
        # Добавляем оригинальную фразу
        variations.append(phrase)
        
        # Вариации с разными падежами/формами
        phrase_words = phrase.split()
        
        # Частичные фразы
        if len(phrase_words) > 2:
            for i in range(len(phrase_words) - 1):
                partial = " ".join(phrase_words[i:i+2])
                if partial not in variations:
                    variations.append(partial)
        
        # Синонимы и альтернативы
        synonyms_map = {
            "схема": ["план", "проект", "программа"],
            "теплоснабжения": ["теплоснабжение", "отопления", "тепловой энергии"],
            "инвестиционная": ["инвестиционных", "капитальных вложений"],
            "программа": ["план", "проект", "схема"],
            "организация": ["компания", "предприятие", "субъект"],
            "регулирование": ["контроль", "управление", "надзор"]
        }
        
        for word, synonyms in synonyms_map.items():
            if word in phrase.lower():
                for synonym in synonyms:
                    variation = phrase.lower().replace(word, synonym)
                    if variation not in variations:
                        variations.append(variation)
        
        return variations[:10]  # Ограничиваем количество вариаций
    
    async def analyze_missing_critical_content(self) -> Dict[str, Any]:
        """Анализирует отсутствующий критический контент."""
        missing_analysis = {
            "missing_phrases": [],
            "partially_found": [],
            "recommendations": []
        }
        
        for phrase in self.critical_phrases:
            logger.info(f"🔍 Проверяем наличие: {phrase}")
            
            exact_matches = await self.find_exact_content_matches(phrase)
            phrase_variations = await self.find_phrase_variations_search(phrase)
            
            if not exact_matches and not phrase_variations:
                missing_analysis["missing_phrases"].append({
                    "phrase": phrase,
                    "search_attempts": len(self.generate_phrase_variations(phrase)),
                    "recommendation": f"Необходимо добавить контент о: {phrase}"
                })
            elif exact_matches or len(phrase_variations) < 3:
                missing_analysis["partially_found"].append({
                    "phrase": phrase,
                    "exact_matches": len(exact_matches),
                    "variations_found": len(phrase_variations),
                    "recommendation": f"Контент найден частично для: {phrase}"
                })
        
        return missing_analysis
    
    async def find_exact_content_matches(self, phrase: str) -> List[Dict[str, Any]]:
        """Ищет точные совпадения контента."""
        return await self.find_document_content(phrase)
    
    async def find_phrase_variations_search(self, phrase: str) -> List[Dict[str, Any]]:
        """Ищет вариации фразы."""
        variations = self.generate_phrase_variations(phrase)
        found_variations = []
        
        for variation in variations:
            results = await self.find_document_content(variation)
            if results:
                found_variations.extend(results)
        
        return found_variations
    
    async def test_search_approaches(self) -> Dict[str, Any]:
        """Тестирует различные подходы к поиску."""
        test_results = {
            "exact_search": {},
            "partial_search": {},
            "semantic_search": {},
            "performance_summary": {}
        }
        
        test_phrase = self.critical_phrases  # Тестируем на первой фразе
        
        # Точный поиск
        exact_results = await self.find_document_content(test_phrase)
        test_results["exact_search"] = {
            "phrase": test_phrase,
            "results_count": len(exact_results),
            "success": len(exact_results) > 0
        }
        
        # Частичный поиск
        partial_phrase = " ".join(test_phrase.split()[:2])
        partial_results = await self.find_document_content(partial_phrase)
        test_results["partial_search"] = {
            "phrase": partial_phrase,
            "results_count": len(partial_results),
            "success": len(partial_results) > 0
        }
        
        # Семантический поиск (через вопрос)
        semantic_question = f"Расскажите о {test_phrase}"
        try:
            if self.storage_manager:
                semantic_results = await self.storage_manager.search_documents(semantic_question, limit=3)
                test_results["semantic_search"] = {
                    "question": semantic_question,
                    "results_count": len(semantic_results),
                    "success": len(semantic_results) > 0
                }
        except Exception as e:
            test_results["semantic_search"] = {"error": str(e)}
        
        return test_results
    
    # === АНАЛИЗ КОНТЕНТА ===
    
    async def quick_content_audit(self) -> Dict[str, Any]:
        """Быстрый аудит контента."""
        logger.info("⚡ Запуск быстрого аудита контента...")
        
        audit_results = {
            "corpus_analysis": await self.analyze_document_corpus(),
            "basic_search_test": await self.test_basic_search(),
            "critical_phrase_analysis": await self.detailed_phrase_analysis(),
            "segmentation_issues": await self.analyze_segmentation_issues()
        }
        
        return audit_results
    
    async def analyze_document_corpus(self) -> Dict[str, Any]:
        """Анализирует корпус документов."""
        if not self.storage_manager:
            await self.initialize_storage_manager()
        
        corpus_analysis = {
            "test_searches": {},
            "document_availability": "unknown",
            "estimated_corpus_size": "unknown"
        }
        
        # Тестовые поиски для оценки размера корпуса
        test_terms = ["документ", "статья", "пункт", "закон", "постановление"]
        
        for term in test_terms:
            try:
                results = await self.storage_manager.search_documents(term, limit=10)
                corpus_analysis["test_searches"][term] = {
                    "results_count": len(results),
                    "available": len(results) > 0
                }
            except Exception as e:
                corpus_analysis["test_searches"][term] = {"error": str(e)}
        
        # Оценка доступности документов
        successful_searches = sum(
            1 for result in corpus_analysis["test_searches"].values() 
            if isinstance(result, dict) and result.get("available", False)
        )
        
        if successful_searches > len(test_terms) * 0.8:
            corpus_analysis["document_availability"] = "good"
        elif successful_searches > len(test_terms) * 0.5:
            corpus_analysis["document_availability"] = "moderate"  
        else:
            corpus_analysis["document_availability"] = "poor"
        
        return corpus_analysis
    
    async def test_basic_search(self) -> Dict[str, Any]:
        """Тестирует базовый поиск."""
        search_test = {
            "phrase_tests": {},
            "success_rate": 0.0,
            "total_phrases": len(self.critical_phrases)
        }
        
        successful_searches = 0
        
        for phrase in self.critical_phrases:
            try:
                results = await self.find_document_content(phrase)
                search_test["phrase_tests"][phrase] = {
                    "found": len(results) > 0,
                    "results_count": len(results),
                    "top_relevance": results.get("relevance_score", 0.0) if results else 0.0
                }
                
                if results:
                    successful_searches += 1
                    
            except Exception as e:
                search_test["phrase_tests"][phrase] = {"error": str(e)}
        
        search_test["success_rate"] = (successful_searches / len(self.critical_phrases)) * 100
        
        return search_test
    
    async def detailed_phrase_analysis(self) -> Dict[str, Any]:
        """Детальный анализ фраз."""
        phrase_analysis = {
            "phrase_details": {},
            "alternative_searches": {},
            "recommendations": []
        }
        
        for phrase in self.critical_phrases[:3]:  # Ограничиваем для скорости
            logger.info(f"🔬 Детальный анализ: {phrase}")
            
            # Основной поиск
            main_results = await self.find_document_content(phrase)
            
            # Альтернативные поиски
            alternatives = self.generate_alternatives(phrase)
            alternative_results = {}
            
            for alt in alternatives:
                alt_results = await self.find_document_content(alt)
                alternative_results[alt] = len(alt_results)
            
            phrase_analysis["phrase_details"][phrase] = {
                "main_search_results": len(main_results),
                "alternatives_tested": len(alternatives),
                "successful_alternatives": sum(1 for count in alternative_results.values() if count > 0)
            }
            
            phrase_analysis["alternative_searches"][phrase] = alternative_results
            
            # Рекомендации
            if not main_results and not any(alternative_results.values()):
                phrase_analysis["recommendations"].append(
                    f"❌ Фраза '{phrase}' требует добавления контента"
                )
            elif not main_results and any(alternative_results.values()):
                phrase_analysis["recommendations"].append(
                    f"⚠️ Фраза '{phrase}' найдена только через альтернативы"
                )
            else:
                phrase_analysis["recommendations"].append(
                    f"✅ Фраза '{phrase}' найдена успешно"
                )
        
        return phrase_analysis
    
    def generate_alternatives(self, phrase: str) -> List[str]:
        """Генерирует альтернативы для поиска."""
        alternatives = []
        
        # Ключевые слова из фразы
        words = phrase.split()
        if len(words) > 1:
            alternatives.extend(words)
        
        # Частичные фразы
        if len(words) > 2:
            alternatives.append(" ".join(words[:2]))
            alternatives.append(" ".join(words[-2:]))
        
        # Синонимичные варианты
        synonyms = {
            "схема теплоснабжения": ["план теплоснабжения", "система теплоснабжения"],
            "инвестиционная программа": ["программа инвестиций", "план инвестиций"],
            "единая теплоснабжающая организация": ["ЕТО", "теплоснабжающая организация"]
        }
        
        if phrase in synonyms:
            alternatives.extend(synonyms[phrase])
        
        return list(set(alternatives))  # Удаляем дубликаты
    
    async def analyze_segmentation_issues(self) -> Dict[str, Any]:
        """Анализирует проблемы сегментации."""
        segmentation_analysis = {
            "long_phrase_tests": {},
            "word_boundary_tests": {},
            "recommendations": []
        }
        
        # Тесты длинных фраз
        long_phrases = [phrase for phrase in self.critical_phrases if len(phrase.split()) > 3]
        
        for phrase in long_phrases:
            full_results = await self.find_document_content(phrase)
            partial_results = await self.find_document_content(" ".join(phrase.split()[:2]))
            
            segmentation_analysis["long_phrase_tests"][phrase] = {
                "full_phrase_results": len(full_results),
                "partial_phrase_results": len(partial_results),
                "segmentation_issue": len(partial_results) > len(full_results) * 2
            }
        
        return segmentation_analysis
    
    # === ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ ===
    
    def generate_improvement_recommendations(self, coverage_analysis: Dict, 
                                           missing_analysis: Dict) -> List[Dict[str, str]]:
        """Генерирует рекомендации по улучшению."""
        recommendations = []
        
        # Анализ покрытия
        coverage_pct = coverage_analysis.get("coverage_statistics", {}).get("coverage_percentage", 0)
        
        if coverage_pct < 50:
            recommendations.append({
                "type": "critical",
                "title": "Низкое покрытие контента",
                "description": f"Только {coverage_pct:.1f}% критических фраз найдено",
                "action": "Необходимо добавить больше документов или улучшить извлечение"
            })
        elif coverage_pct < 80:
            recommendations.append({
                "type": "warning", 
                "title": "Умеренное покрытие контента",
                "description": f"Найдено {coverage_pct:.1f}% критических фраз",
                "action": "Рекомендуется добавить дополнительный контент"
            })
        else:
            recommendations.append({
                "type": "success",
                "title": "Хорошее покрытие контента",
                "description": f"Найдено {coverage_pct:.1f}% критических фраз",
                "action": "Продолжайте поддерживать качество контента"
            })
        
        # Анализ отсутствующего контента
        missing_count = len(missing_analysis.get("missing_phrases", []))
        if missing_count > 0:
            recommendations.append({
                "type": "action",
                "title": f"Отсутствует {missing_count} критических фраз",
                "description": "Некоторые важные термины не найдены в документах",
                "action": "Проверьте загрузку документов и качество извлечения текста"
            })
        
        return recommendations
    
    # === ОСНОВНЫЕ МЕТОДЫ ===
    
    async def run_basic_diagnostics(self) -> Dict[str, Any]:
        """Запускает базовую диагностику."""
        logger.info("🔍 Запуск базовой диагностики поиска...")
        
        results = {
            "content_search": {}
        }
        
        # Тестируем поиск контента
        for phrase in self.critical_phrases[:3]:
            content_results = await self.find_document_content(phrase)
            results["content_search"][phrase] = {
                "found_documents": len(content_results),
                "documents": content_results
            }
        
        return results
    
    async def run_advanced_diagnostics(self) -> Dict[str, Any]:
        """Запускает продвинутую диагностику."""
        return await self.comprehensive_search_analysis()
    
    async def run_content_audit(self) -> Dict[str, Any]:
        """Запускает аудит контента."""
        return await self.quick_content_audit()
    
    async def run_full_diagnostics(self) -> Dict[str, Any]:
        """Запускает полную диагностику."""
        logger.info("🚀 Запуск полной диагностики...")
        
        return {
            "basic_diagnostics": await self.run_basic_diagnostics(),
            "advanced_diagnostics": await self.run_advanced_diagnostics(),
            "content_audit": await self.run_content_audit(),
            "timestamp": str(asyncio.get_event_loop().time())
        }
    
    def generate_diagnostic_report(self, results: Dict[str, Any], 
                                 output_file: str = "search_diagnostics_report.json"):
        """Генерирует отчет по диагностике."""
        logger.info(f"📊 Сохраняем отчет в {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Краткий отчет в консоль
        print("\n" + "="*60)
        print("🔍 ОТЧЕТ ПО ДИАГНОСТИКЕ ПОИСКА")
        print("="*60)
        
        # Статистика по базовой диагностике
        if "basic_diagnostics" in results:
            basic = results["basic_diagnostics"]
            if "keyword_search" in basic:
                keyword_stats = basic["keyword_search"]["summary"]
                print(f"🔑 Найдено ключевых слов: {keyword_stats.get('found_keywords', 0)}")
                print(f"📄 Всего документов: {keyword_stats.get('total_documents', 0)}")
        
        # Статистика по продвинутой диагностике
        if "advanced_diagnostics" in results:
            advanced = results["advanced_diagnostics"]
            if "document_coverage" in advanced:
                coverage = advanced["document_coverage"]["coverage_statistics"]
                print(f"📊 Покрытие контента: {coverage.get('coverage_percentage', 0):.1f}%")
        
        # Рекомендации
        if "advanced_diagnostics" in results and "recommendations" in results["advanced_diagnostics"]:
            recommendations = results["advanced_diagnostics"]["recommendations"]
            print(f"\n💡 Рекомендации ({len(recommendations)}):")
            for rec in recommendations[:3]:
                print(f"  • {rec.get('title', 'Без названия')}")
        
        print(f"\n💾 Полный отчет сохранен в: {output_file}")
        print("="*60)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Search & Content Diagnostics Suite")
    parser.add_argument(
        "--mode", 
        choices=["basic", "advanced", "content", "full"], 
        default="full",
        help="Режим диагностики"
    )
    parser.add_argument(
        "--output", 
        default="search_diagnostics_report.json",
        help="Файл для отчета"
    )
    
    args = parser.parse_args()
    
    suite = SearchDiagnosticsSuite()
    
    try:
        if args.mode == "basic":
            results = await suite.run_basic_diagnostics()
        elif args.mode == "advanced":
            results = await suite.run_advanced_diagnostics()
        elif args.mode == "content":
            results = await suite.run_content_audit()
        else:  # full
            results = await suite.run_full_diagnostics()
        
        suite.generate_diagnostic_report(results, args.output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка диагностики: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
