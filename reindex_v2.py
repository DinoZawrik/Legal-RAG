"""Re-index PostgreSQL chunks into ChromaDB. Resume-capable, sync httpx."""
import json
import time
import psycopg2
import httpx
import chromadb

BATCH_SIZE = 20
PG_DSN = "postgresql://legal_rag_user:LegalRag2024_Secure!@localhost:5432/legal_rag_db"
EMBEDDINGS_URL = "http://localhost:8001/v1/embeddings"
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
COLLECTION_NAME = "documents"


def get_embeddings(texts, client):
    for attempt in range(5):
        try:
            r = client.post(EMBEDDINGS_URL, json={"input": texts}, timeout=120)
            r.raise_for_status()
            return [item["embedding"] for item in r.json()["data"]]
        except Exception as e:
            print(f"      embed retry {attempt+1}/5: {e}")
            time.sleep(10 * (attempt + 1))
    return None


def main():
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()
    chroma = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = chroma.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    # Get already-indexed IDs
    existing = set()
    try:
        result = collection.get(include=[])
        existing = set(result["ids"])
    except Exception:
        pass
    print(f"Already in ChromaDB: {len(existing)} chunks")

    cur.execute("SELECT d.id, d.filename FROM documents d WHERE d.status='completed'")
    docs = cur.fetchall()
    print(f"Documents to index: {len(docs)}")

    http = httpx.Client(timeout=120)
    total_added = 0

    for doc_id, filename in docs:
        cur.execute(
            "SELECT id, chunk_index, text, metadata FROM chunks WHERE document_id=%s ORDER BY chunk_index",
            (str(doc_id),),
        )
        rows = cur.fetchall()
        # Filter out already indexed
        rows = [r for r in rows if str(r[0]) not in existing]
        if not rows:
            print(f"  {filename}: all chunks already indexed, skip")
            continue
        print(f"  {filename}: {len(rows)} new chunks to index")

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            texts = [r[2] for r in batch]

            embeddings = get_embeddings(texts, http)
            if embeddings is None:
                print(f"    FAILED batch at {i}, skipping")
                continue

            ids, docs_text, metas = [], [], []
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
                ids.append(str(chunk_id))
                docs_text.append(text)
                metas.append(chroma_meta)

            collection.add(ids=ids, documents=docs_text, embeddings=embeddings, metadatas=metas)
            total_added += len(batch)
            done = min(i + BATCH_SIZE, len(rows))
            if done % 200 == 0 or done == len(rows):
                print(f"    {done}/{len(rows)} (+{total_added} total)")
            time.sleep(0.5)  # small delay to avoid overwhelming embeddings server

    http.close()
    print(f"\nDone! ChromaDB total: {collection.count()} chunks")
    conn.close()


if __name__ == "__main__":
    main()
