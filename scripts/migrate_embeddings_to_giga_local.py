#!/usr/bin/env python3
"""
🔄 Миграция ChromaDB векторов на Giga-Embeddings

ИСПОЛЬЗОВАНИЕ:
    1. Запустить embeddings сервер:
       docker-compose -f docker-compose.embeddings.yml up -d

    2. Проверить размерность:
       python test_embeddings_server.py

    3. Если размерность != 768, запустить миграцию:
       python scripts/migrate_embeddings_to_giga_local.py

ВАЖНО: Этот скрипт нужен ТОЛЬКО если размерность Giga-Embeddings != 768!
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.giga_local_embeddings_client import GigaLocalEmbeddingsClient
from core.vector_store_manager import VectorStoreManager
import chromadb
from chromadb.config import Settings as ChromaSettings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    print("=" * 80)
    print("🔄 МИГРАЦИЯ CHROMADB ВЕКТОРОВ НА GIGA-EMBEDDINGS")
    print("=" * 80)

    # 1. Проверка embeddings сервера
    print("\n[1/6] Проверка embeddings сервера...")
    embeddings_client = GigaLocalEmbeddingsClient()

    try:
        health = await embeddings_client.health_check()
        if not health.get("model_loaded"):
            print("❌ ОШИБКА: Модель не загружена!")
            return

        info = await embeddings_client.get_model_info()
        new_dimension = info["embedding_dimension"]

        print(f"✅ Embeddings сервер готов")
        print(f"   Модель: {info['model_name']}")
        print(f"   Размерность: {new_dimension}")

    except Exception as e:
        print(f"❌ Embeddings сервер недоступен: {e}")
        return

    # 2. Подключение к ChromaDB
    print("\n[2/6] Подключение к ChromaDB...")
    chroma_client = chromadb.HttpClient(
        host="localhost",
        port=8000,
        settings=ChromaSettings(allow_reset=False)
    )

    try:
        old_collection = chroma_client.get_collection("documents")
        doc_count = old_collection.count()
        print(f"✅ Найдена коллекция 'documents': {doc_count} документов")

    except Exception as e:
        print(f"❌ Не удалось получить коллекцию: {e}")
        return

    if doc_count == 0:
        print("⚠️  Коллекция пустая, миграция не требуется")
        return

    # 3. Получение всех документов
    print(f"\n[3/6] Извлечение {doc_count} документов...")
    try:
        all_data = old_collection.get(include=["documents", "metadatas"])
        ids = all_data["ids"]
        documents = all_data["documents"]
        metadatas = all_data["metadatas"]

        print(f"✅ Извлечено {len(ids)} документов")

    except Exception as e:
        print(f"❌ Ошибка извлечения: {e}")
        return

    # 4. Генерация новых embeddings
    print(f"\n[4/6] Генерация новых embeddings ({new_dimension}-dim)...")
    print(f"   Это может занять 10-30 минут для {len(documents)} документов...")

    batch_size = 50
    new_embeddings = []

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        try:
            batch_embeddings = await embeddings_client.generate_embeddings(batch)
            new_embeddings.extend(batch_embeddings)

            progress = (i + len(batch)) / len(documents) * 100
            print(f"   Прогресс: {progress:.1f}% ({i + len(batch)}/{len(documents)})")

        except Exception as e:
            print(f"❌ Ошибка генерации батча {i // batch_size}: {e}")
            return

    print(f"✅ Сгенерировано {len(new_embeddings)} embeddings")

    # 5. Создание новой коллекции
    print(f"\n[5/6] Создание новой коллекции 'documents_giga'...")
    try:
        # Удалить если существует
        try:
            chroma_client.delete_collection("documents_giga")
        except:
            pass

        new_collection = chroma_client.create_collection(
            name="documents_giga",
            metadata={"hnsw:space": "cosine"}
        )

        # Добавление данных батчами
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_embeddings = new_embeddings[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]

            new_collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_docs,
                metadatas=batch_meta
            )

            progress = (i + len(batch_ids)) / len(ids) * 100
            print(f"   Загрузка: {progress:.1f}% ({i + len(batch_ids)}/{len(ids)})")

        print(f"✅ Создана новая коллекция: {new_collection.count()} документов")

    except Exception as e:
        print(f"❌ Ошибка создания коллекции: {e}")
        return

    # 6. Атомарная замена коллекций
    print(f"\n[6/6] Замена коллекций...")
    try:
        chroma_client.delete_collection("documents")
        print(f"✅ Удалена старая коллекция 'documents'")

        # ВАЖНО: ChromaDB не поддерживает rename, поэтому создаем новую с тем же именем
        final_collection = chroma_client.create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )

        # Копируем данные из documents_giga
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_embeddings = new_embeddings[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]

            final_collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_docs,
                metadatas=batch_meta
            )

        # Удаляем временную
        chroma_client.delete_collection("documents_giga")

        print(f"✅ Миграция завершена: {final_collection.count()} документов")

    except Exception as e:
        print(f"❌ Ошибка замены коллекций: {e}")
        print(f"⚠️  ВАЖНО: Старая коллекция удалена, но новая 'documents' не создана!")
        print(f"   Восстановите из 'documents_giga' вручную")
        return

    # Итоговый отчет
    print("\n" + "=" * 80)
    print("🎉 МИГРАЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
    print("=" * 80)
    print(f"✅ Старая коллекция (Gemini 768-dim): удалена")
    print(f"✅ Новая коллекция (Giga {new_dimension}-dim): {final_collection.count()} документов")
    print(f"\n🚀 СЛЕДУЮЩИЕ ШАГИ:")
    print(f"   1. Обновить код: VectorStoreManager уже использует локальный сервер")
    print(f"   2. Запустить тесты: python test_40_natural_answers.py")
    print(f"   3. Сравнить качество с baseline (39/40 Gemini)")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
