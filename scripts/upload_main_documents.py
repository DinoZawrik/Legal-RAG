#!/usr/bin/env python3
"""
Загрузка основных документов в Docker ChromaDB систему
"""
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai
import chromadb
from chromadb.config import Settings
import PyPDF2
import requests
import time

def test_docker_chromadb_connection():
    """Тестирование подключения к Docker ChromaDB"""
    print("=== ТЕСТИРОВАНИЕ DOCKER CHROMADB ===")

    # Проверяем HTTP API
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        if response.status_code == 200:
            print("+ ChromaDB HTTP API отвечает")
            return True
        else:
            print(f"- ChromaDB HTTP ошибка: {response.status_code}")
    except Exception as e:
        print(f"- ChromaDB HTTP недоступен: {e}")

    return False

def connect_to_docker_chromadb():
    """Подключение к ChromaDB в Docker"""
    print("Подключение к Docker ChromaDB...")

    try:
        # Подключение к ChromaDB через HTTP
        client = chromadb.HttpClient(
            host="localhost",
            port=8000,
            settings=Settings(allow_reset=True)
        )

        # Проверяем подключение
        collections = client.list_collections()
        print(f"+ Подключение успешно. Коллекций: {len(collections)}")

        return client
    except Exception as e:
        print(f"- Ошибка подключения к Docker ChromaDB: {e}")
        return None

def extract_pdf_text(pdf_path):
    """Извлечение текста из PDF"""
    print(f"Извлечение текста из: {pdf_path}")

    try:
        chunks = []
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            current_chunk = ""
            chunk_size = 2000

            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    page_text = ' '.join(page_text.split())
                    current_chunk += f" {page_text}"

                    if len(current_chunk) >= chunk_size:
                        chunks.append(current_chunk.strip())
                        current_chunk = ""

                except Exception as e:
                    print(f"   Ошибка страницы {page_num}: {e}")
                    continue

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

        print(f"   Создано чанков: {len(chunks)}")
        return chunks

    except Exception as e:
        print(f"   Ошибка PDF: {e}")
        return []

def upload_to_docker_chromadb():
    """Загрузка документов в Docker ChromaDB"""
    print("=== ЗАГРУЗКА В DOCKER CHROMADB ===")

    load_dotenv()
    embedding_model = os.getenv('EMBEDDING_MODEL', 'models/text-embedding-004')
    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("ОШИБКА: GEMINI_API_KEY не найден")
        return False

    # Подключение к Docker ChromaDB
    client = connect_to_docker_chromadb()
    if not client:
        print("ОШИБКА: Не удалось подключиться к Docker ChromaDB")
        return False

    genai.configure(api_key=api_key)

    # Создаем коллекцию в Docker ChromaDB
    collection_name = "docker_legal_documents"

    try:
        # Пытаемся получить существующую коллекцию
        try:
            collection = client.get_collection(collection_name)
            print(f"Найдена существующая коллекция: {collection_name}")
            # Очищаем для свежих данных
            try:
                client.delete_collection(collection_name)
                print("Старая коллекция удалена")
            except:
                pass
        except:
            pass

        # Создаем новую коллекцию
        collection = client.create_collection(collection_name)
        print(f"Создана новая коллекция: {collection_name}")

    except Exception as e:
        print(f"ОШИБКА создания коллекции: {e}")
        return False

    # Документы для загрузки
    documents = [
        {
            "path": "файлы_для_теста/Федеральный закон от 21.07.2005 N 115-ФЗ (ред. от 23.07.2025.pdf",
            "name": "115-ФЗ"
        },
        {
            "path": "файлы_для_теста/Федеральный закон от 13.07.2015 N 224-ФЗ (ред. от 31.07.2025 (1).pdf",
            "name": "224-ФЗ"
        }
    ]

    total_chunks = 0

    for doc_info in documents:
        if not os.path.exists(doc_info["path"]):
            print(f"ПРОПУСКАЕМ: {doc_info['path']} не найден")
            continue

        print(f"\\nОбработка: {doc_info['name']}")

        # Извлекаем текст
        text_chunks = extract_pdf_text(doc_info["path"])

        if not text_chunks:
            print(f"ОШИБКА: не удалось извлечь текст из {doc_info['name']}")
            continue

        # Создаем эмбеддинги и загружаем в ChromaDB
        embeddings = []
        documents_list = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(text_chunks):
            try:
                if len(chunk) > 3000:
                    chunk = chunk[:3000] + "..."

                print(f"   Эмбеддинг {i+1}/{len(text_chunks)}")

                result = genai.embed_content(
                    model=embedding_model,
                    content=chunk,
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )

                if result and 'embedding' in result:
                    embedding = result['embedding']

                    if len(embedding) != 768:
                        print(f"   ОШИБКА: размерность {len(embedding)} != 768")
                        continue

                    embeddings.append(embedding)
                    documents_list.append(chunk)
                    metadatas.append({
                        'source': doc_info['name'],
                        'chunk_index': i,
                        'total_chunks': len(text_chunks),
                        'document_type': 'legal',
                        'processed_by': 'docker_upload'
                    })
                    ids.append(f"{doc_info['name']}_chunk_{i}")

            except Exception as e:
                print(f"   ОШИБКА эмбеддинга {i}: {e}")
                continue

        if embeddings:
            try:
                # Загружаем в Docker ChromaDB
                collection.add(
                    embeddings=embeddings,
                    documents=documents_list,
                    metadatas=metadatas,
                    ids=ids
                )

                print(f"   + Загружено в Docker ChromaDB: {len(embeddings)} эмбеддингов")
                total_chunks += len(embeddings)

            except Exception as e:
                print(f"   ОШИБКА загрузки в ChromaDB: {e}")
        else:
            print(f"   ОШИБКА: не создано эмбеддингов для {doc_info['name']}")

    print(f"\\n=== ИТОГО ===")
    print(f"Всего загружено в Docker ChromaDB: {total_chunks} чанков")

    if total_chunks > 0:
        print("+ DOCKER CHROMADB ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
        return True
    else:
        print("- НЕ УДАЛОСЬ ЗАГРУЗИТЬ ДОКУМЕНТЫ")
        return False

if __name__ == "__main__":
    # Сначала проверяем доступность Docker ChromaDB
    if test_docker_chromadb_connection():
        success = upload_to_docker_chromadb()
    else:
        print("КРИТИЧНО: Docker ChromaDB недоступна!")
        print("Запустите: docker-compose -f docker-compose.microservices.yml up -d chromadb")
        success = False

    exit(0 if success else 1)