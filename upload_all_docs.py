"""Upload all demo documents to the system and reindex into ChromaDB."""
import httpx
import asyncio
import aiohttp
import json
import os
import psycopg2
import chromadb

API = "http://localhost:8080"
EMBEDDINGS_URL = "http://localhost:8001/v1/embeddings"
PG_DSN = "postgresql://legal_rag_user:LegalRag2024_Secure!@localhost:5432/legal_rag_db"
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
COLLECTION_NAME = "documents"
BATCH_SIZE = 30

DEMO_DIR = r"C:\Users\79103\Repositorii\Legal-RAG\demo_documents"
DEMO_FILES = [
    "grazhdanskij_kodeks_rf.txt",
    "semejnyj_kodeks_rf.txt",
    "zakon_o_zashite_prav_potrebitelej.txt",
    "labor_code_excerpt.txt",
    "zhilishchnyj_kodeks_rf.txt",
]


def get_token():
    r = httpx.post(f"{API}/admin/auth/login", json={"username": "admin", "password": "Admin2024_Secure!"}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def delete_all_docs(token):
    # Delete from PostgreSQL directly
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()
    cur.execute("DELETE FROM chunks")
    cur.execute("DELETE FROM documents")
    conn.commit()
    print(f"Cleared PostgreSQL: chunks and documents tables")
    conn.close()

    # Delete ChromaDB collection
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    try:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted old ChromaDB collection")
    except Exception:
        print("No ChromaDB collection to delete")
    client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    print("Created fresh ChromaDB collection")


def upload_docs(token):
    headers = {"Authorization": f"Bearer {token}"}
    doc_ids = []
    for fname in DEMO_FILES:
        fpath = os.path.join(DEMO_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP {fname} - not found")
            continue
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  Uploading {fname} ({size_kb:.0f} KB)...")
        with open(fpath, "rb") as f:
            files = {"file": (fname, f, "text/plain")}
            data = {
                "original_filename": fname,
                "auto_process": "true",
                "async_processing": "false",
            }
            r = httpx.post(f"{API}/api/upload", headers=headers, files=files, data=data, timeout=600)
        resp = r.json()
        if resp.get("success"):
            doc_id = resp.get("document_id", "?")
            chunks = resp.get("chunks_created", "?")
            print(f"    OK: doc_id={doc_id}, chunks={chunks}")
            doc_ids.append(doc_id)
        else:
            print(f"    FAIL: {resp}")
    return doc_ids


async def get_embeddings(texts):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            EMBEDDINGS_URL,
            json={"input": texts},
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            data = await resp.json()
            return [item["embedding"] for item in data["data"]]


async def reindex_all():
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()

    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = client.get_collection(name=COLLECTION_NAME)

    # Get all documents
    cur.execute("SELECT id, filename FROM documents WHERE status = 'completed'")
    documents = cur.fetchall()
    print(f"\nReindexing {len(documents)} documents...")

    for doc_id, filename in documents:
        cur.execute(
            "SELECT id, chunk_index, text, metadata FROM chunks WHERE document_id = %s ORDER BY chunk_index",
            (doc_id,)
        )
        rows = cur.fetchall()
        if not rows:
            print(f"  {filename}: 0 chunks, skipping")
            continue
        print(f"  {filename}: {len(rows)} chunks")

        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start:batch_start + BATCH_SIZE]
            texts = [r[2] for r in batch]

            for attempt in range(3):
                try:
                    embeddings = await get_embeddings(texts)
                    break
                except Exception as e:
                    print(f"    Retry {attempt+1}/3: {e}")
                    await asyncio.sleep(5)
            else:
                print(f"    FAILED batch at {batch_start}, skipping")
                continue

            ids = []
            documents_text = []
            metadatas = []
            for row in batch:
                chunk_id, chunk_index, text, meta_json = row
                meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
                chroma_meta = {
                    "source": filename,
                    "chunk_index": chunk_index,
                    "chunk_type": meta.get("chunk_type", "text"),
                    "original_filename": filename,
                    "document_id": str(doc_id),
                }
                if "article_number" in meta:
                    chroma_meta["article_number"] = str(meta["article_number"])
                if "law" in meta:
                    chroma_meta["law"] = meta["law"]
                ids.append(str(chunk_id))
                documents_text.append(text)
                metadatas.append(chroma_meta)

            collection.add(
                ids=ids,
                documents=documents_text,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            done = min(batch_start + BATCH_SIZE, len(rows))
            if done % 300 == 0 or done == len(rows):
                print(f"    {done}/{len(rows)}")

    print(f"\nChromaDB total: {collection.count()} chunks")
    conn.close()


def main():
    print("=== Step 1: Auth ===")
    token = get_token()
    print("Got token")

    print("\n=== Step 2: Delete old docs ===")
    delete_all_docs(token)

    print("\n=== Step 3: Upload demo documents ===")
    upload_docs(token)

    print("\n=== Step 4: Reindex into ChromaDB ===")
    asyncio.run(reindex_all())

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
