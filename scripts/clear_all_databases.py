#!/usr/bin/env python3
"""
Script for clearing all databases
"""
import asyncio
import os
import sys
import logging
from datetime import datetime

from core.logging_config import configure_logging

logger = logging.getLogger(__name__)

async def clear_postgresql():
    """Очистка PostgreSQL"""
    try:
        import psycopg2
        
        # Параметры подключения
        conn_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', 5432),
            'database': os.getenv('POSTGRES_DB', 'legal_rag_db'),
            'user': os.getenv('POSTGRES_USER', 'legal_rag_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'change_me_in_env')
        }
        
        logger.info(f"🔄 Подключаюсь к PostgreSQL: {conn_params['host']}:{conn_params['port']}")
        
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        
        # Получаем список таблиц
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        logger.info(f"📋 Найдено таблиц: {len(tables)}")
        
        # Очищаем таблицы
        total_deleted = 0
        for table in tables:
            try:
                # Подсчитываем записи
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                
                if count > 0:
                    # Удаляем записи
                    cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                    logger.info(f"✅ Таблица {table}: удалено {count} записей")
                    total_deleted += count
                else:
                    logger.info(f"📊 Таблица {table}: уже пуста")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка очистки таблицы {table}: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ PostgreSQL очищен. Всего удалено записей: {total_deleted}")
        return total_deleted
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки PostgreSQL: {e}")
        return 0

async def clear_redis():
    """Очистка Redis"""
    try:
        import redis
        
        # Подключение к Redis
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', 6379))
        db = int(os.getenv('REDIS_DB', 0))
        
        logger.info(f"🔄 Подключаюсь к Redis: {host}:{port}")
        
        r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        
        # Проверяем подключение
        r.ping()
        
        # Подсчитываем ключи
        keys_count = r.dbsize()
        
        if keys_count > 0:
            # Очищаем все ключи
            r.flushdb()
            logger.info(f"✅ Redis очищен. Удалено ключей: {keys_count}")
        else:
            logger.info("📊 Redis уже пуст")
            
        return keys_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки Redis: {e}")
        return 0

async def clear_chromadb():
    """Очистка ChromaDB"""
    try:
        import chromadb
        
        # Подключение к ChromaDB
        host = os.getenv('CHROMA_HOST', 'localhost')
        port = int(os.getenv('CHROMA_PORT', 8000))
        
        logger.info(f"🔄 Подключаюсь к ChromaDB: http://{host}:{port}")
        
        # Создаем клиент
        client = chromadb.HttpClient(host=host, port=port)
        
        # Получаем список коллекций
        collections = client.list_collections()
        
        logger.info(f"📋 Найдено коллекций: {len(collections)}")
        
        total_documents = 0
        for collection in collections:
            try:
                # Подсчитываем документы
                count = collection.count()
                total_documents += count
                
                # Удаляем коллекцию
                client.delete_collection(collection.name)
                logger.info(f"✅ Коллекция {collection.name}: удалено {count} документов")
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка очистки коллекции {collection.name}: {e}")
        
        logger.info(f"✅ ChromaDB очищен. Всего удалено документов: {total_documents}")
        return total_documents
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки ChromaDB: {e}")
        return 0

async def main():
    """Основная функция"""
    logger.info("🗑️ Начинаю полную очистку баз данных LegalRAG")
    start_time = datetime.now()
    
    results = {}
    
    # Очистка PostgreSQL
    results['postgresql_records'] = await clear_postgresql()
    
    # Очистка Redis
    results['redis_keys'] = await clear_redis()
    
    # Очистка ChromaDB
    results['chromadb_documents'] = await clear_chromadb()
    
    # Подводим итоги
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("=" * 60)
    logger.info("🧹 РЕЗУЛЬТАТЫ ОЧИСТКИ БАЗЫ ДАННЫХ")
    logger.info("=" * 60)
    logger.info(f"⏱️ Время выполнения: {duration:.1f}с")
    logger.info(f"🗄️ PostgreSQL записей удалено: {results['postgresql_records']}")
    logger.info(f"🔑 Redis ключей удалено: {results['redis_keys']}")
    logger.info(f"📄 ChromaDB документов удалено: {results['chromadb_documents']}")
    
    total_items = sum(results.values())
    logger.info(f"📊 Общее количество удаленных элементов: {total_items}")
    
    if total_items > 0:
        logger.info("✅ Очистка баз данных завершена успешно!")
    else:
        logger.info("📊 Базы данных были пусты")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("👋 Очистка прервана пользователем")