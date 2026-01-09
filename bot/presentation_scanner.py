#!/usr/bin/env python3
"""
🎯 ИНТЕГРИРОВАННЫЙ СКАНЕР ПРЕЗЕНТАЦИЙ
Интеграция Universal Contextual Extraction v2.0 в основную систему
"""

import asyncio
import aiohttp
import json
import time
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PresentationScanner:
    """Интегрированный сканер презентаций для основной системы."""
    
    def __init__(self, api_gateway_url: str = "http://localhost:8080"):
        self.api_gateway_url = api_gateway_url
        self.scanner_version = "Universal Contextual Extraction v2.0"
    
    async def scan_presentation_full(
        self, 
        file_path: str, 
        original_filename: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Полное постраничное сканирование презентации.
        Возвращает детальные результаты извлечения.
        """
        
        logger.info(f"Starting full presentation scan: {original_filename}")
        start_time = time.time()
        
        try:
            # Сначала читаем файл в память
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Подготавливаем данные для API Gateway
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                
                # Передаем содержимое файла
                data.add_field('file', file_content, filename=original_filename, content_type='application/pdf')
                
                data.add_field('original_filename', original_filename)
                data.add_field('document_type', 'presentation')
                data.add_field('is_presentation', 'true')
                data.add_field('presentation_supplement', 'true')
                data.add_field('contextual_extraction', 'true')  # Включаем контекстное извлечение
                data.add_field('force_reprocess', 'true')  # Принудительная переобработка
                
                # Отправляем запрос на обработку
                async with session.post(
                    f"{self.api_gateway_url}/api/upload",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=int(os.getenv('PRESENTATION_PROCESSING_TIMEOUT', '3600')))  # Увеличен до 1 часа
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API Gateway error: {response.status} - {error_text}")
                        return {
                            'status': 'error',
                            'error': f"API Gateway error: {response.status}",
                            'details': error_text
                        }
                    
                    result = await response.json()
                    processing_time = time.time() - start_time
                    
                    # Анализируем результат
                    return await self._process_scan_result(result, processing_time, original_filename)
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout during presentation scan: {original_filename}")
            return {
                'status': 'error',
                'error': 'Timeout during scanning',
                'processing_time': time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Error during presentation scan: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    async def _process_scan_result(
        self, 
        api_result: Dict[str, Any], 
        processing_time: float,
        filename: str
    ) -> Dict[str, Any]:
        """Обрабатывает результат сканирования от API Gateway."""
        
        # Проверяем наличие контекстуальных данных
        contextual_data = api_result.get('contextual_data', {})
        if contextual_data and 'contextual_chunks' in contextual_data:
            contextual_chunks = contextual_data['contextual_chunks']
            
            # Анализируем результаты
            scan_result = {
                'status': 'success',
                'scanner_version': self.scanner_version,
                'filename': filename,
                'processing_time': processing_time,
                'total_pages': len(contextual_chunks),
                'successful_pages': 0,
                'failed_pages': 0,
                'total_elements': contextual_data.get('total_elements', 0),
                'total_relationships': contextual_data.get('total_relationships', 0),
                'total_insights': contextual_data.get('total_insights', 0),
                'total_text_length': 0,
                'pages': [],
                'summary': []
            }
            
            for i, chunk in enumerate(contextual_chunks):
                try:
                    # Проверяем успешность обработки страницы
                    if chunk.get('metadata', {}).get('parsing_success', True):
                        elements_count = len(chunk.get('elements', []))
                        relationships_count = len(chunk.get('relationships', []))
                        insights_count = len(chunk.get('key_insights', []))
                        text_length = len(chunk.get('searchable_text', ''))
                        
                        scan_result['successful_pages'] += 1
                        scan_result['total_elements'] += elements_count
                        scan_result['total_relationships'] += relationships_count
                        scan_result['total_insights'] += insights_count
                        scan_result['total_text_length'] += text_length
                        
                        page_info = {
                            'page_number': chunk.get('slide_number', i + 1),
                            'slide_title': chunk.get('slide_title', f'Страница {i + 1}'),
                            'slide_type': chunk.get('slide_type', 'unknown'),
                            'elements': elements_count,
                            'relationships': relationships_count,
                            'insights': insights_count,
                            'text_length': text_length,
                            'status': 'success'
                        }
                        
                        scan_result['pages'].append(page_info)
                        
                        # Добавляем в сводку
                        scan_result['summary'].append(
                            f"Страница {page_info['page_number']}: {page_info['slide_title'][:50]}{'...' if len(page_info['slide_title']) > 50 else ''}"
                        )
                        
                    else:
                        scan_result['failed_pages'] += 1
                        fallback_reason = chunk.get('metadata', {}).get('fallback_reason', 'Unknown error')
                        
                        page_info = {
                            'page_number': i + 1,
                            'status': 'failed',
                            'error': fallback_reason
                        }
                        
                        scan_result['pages'].append(page_info)
                        
                except Exception as e:
                    logger.error(f"Error processing chunk {i}: {e}")
                    scan_result['failed_pages'] += 1
            
            # Рассчитываем процент успеха
            scan_result['success_rate'] = (scan_result['successful_pages'] / scan_result['total_pages'] * 100) if scan_result['total_pages'] > 0 else 0
            
            return scan_result
            
        else:
            # Нет контекстуальных данных - возвращаем информацию о базовой обработке
            return {
                'status': 'partial',
                'scanner_version': self.scanner_version,
                'filename': filename,
                'processing_time': processing_time,
                'message': api_result.get('message', 'Document processed without contextual extraction'),
                'api_result': api_result
            }
    
    def format_scan_report(self, scan_result: Dict[str, Any]) -> str:
        """Форматирует отчет о сканировании для пользователя."""
        
        if scan_result['status'] == 'error':
            return f"""ERROR: Ошибка сканирования презентации

Файл: {scan_result.get('filename', 'Unknown')}
Ошибка: {scan_result['error']}
Время: {scan_result.get('processing_time', 0):.1f} секунд

Попробуйте загрузить файл еще раз или обратитесь к администратору."""

        elif scan_result['status'] == 'partial':
            return f"""WARNING: Частичное сканирование презентации

Файл: {scan_result['filename']}
Время: {scan_result['processing_time']:.1f} секунд
Статус: {scan_result['message']}

Документ обработан базовым способом без детального извлечения контекста."""

        elif scan_result['status'] == 'success':
            report = f"""SUCCESS: Полное сканирование презентации завершено

Система: {scan_result['scanner_version']}

Файл: {scan_result['filename']}
Время обработки: {scan_result['processing_time']:.1f} секунд

Результаты сканирования:
- Страниц обработано: {scan_result['successful_pages']}/{scan_result['total_pages']} ({scan_result['success_rate']:.1f}%)
- Найдено элементов: {scan_result['total_elements']}
- Построено связей: {scan_result['total_relationships']}  
- Извлечено выводов: {scan_result['total_insights']}
- Индексированного текста: {scan_result['total_text_length']} символов

Содержание презентации:
"""
            # Добавляем сводку по страницам (первые 10)
            for summary_line in scan_result['summary'][:10]:
                report += f"\n{summary_line}"
            
            if len(scan_result['summary']) > 10:
                report += f"\n... и еще {len(scan_result['summary']) - 10} страниц"
            
            if scan_result['failed_pages'] > 0:
                report += f"\n\nПроблемы: {scan_result['failed_pages']} страниц не удалось обработать полностью"
            
            report += "\n\nПрезентация готова для поиска и анализа!"
            
            return report
        
        else:
            return f"Неизвестный статус сканирования: {scan_result.get('status', 'unknown')}"

# Функция для интеграции в Telegram бота
async def scan_presentation_for_bot(
    file_path: str, 
    original_filename: str,
    api_gateway_url: str = "http://localhost:8080",
    user_id: Optional[int] = None
) -> str:
    """
    Сканирует презентацию и возвращает отформатированный отчет для Telegram бота.
    """
    
    scanner = PresentationScanner(api_gateway_url)
    scan_result = await scanner.scan_presentation_full(file_path, original_filename, user_id)
    return scanner.format_scan_report(scan_result)
