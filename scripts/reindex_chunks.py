"""Re-index ALL PostgreSQL chunks into ChromaDB with embeddings (1024-dim)."""
import asyncio
import json
import psycopg2
import aiohttp
import chromadb

BATCH_SIZE = 30
PG_DSN = "postgresql://legal_rag_user:LegalRag2024_Secure!@localhost:5432/legal_rag_db"
EMBEDDINGS_URL = "http://localhost:8001/v1/embeddings"
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
COLLECTION_NAME = "documents"

DOC_SOURCE_MAP = {
    "8d3e8298-0114-42b5-9918-0c9ff031cc10": "garant_grajdansky_kodeks_rf.pdf",
    "ba3e56ae-3ae3-4d6d-91bc-4b4442cf91a3": "skodeksrf.pdf",
    "d6cc9252-f15b-4fe9-8e0f-31fe08ec261a": "labor_code_excerpt.txt",
    "94bc733d-595b-43ad-ab0c-cfb95cf4863c": "consumer_protection_law.txt",
}


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            EMBEDDINGS_URL,
            json={"input": texts},
            timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            data = await resp.json()
            return [item["embedding"] for item in data["data"]]


async def main():
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()

    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # Get existing IDs to skip
    existing = set(collection.get(include=[])["ids"])
    print(f"ChromaDB has {len(existing)} chunks, resuming...")

    for doc_id, source_name in DOC_SOURCE_MAP.items():
        cur.execute(
            "SELECT id, chunk_index, text, metadata FROM chunks WHERE document_id = %s ORDER BY chunk_index",
            (doc_id,)
        )
        rows = cur.fetchall()
        # Filter out already-indexed
        rows = [r for r in rows if str(r[0]) not in existing]
        if not rows:
            print(f"\n{source_name}: already fully indexed, skipping")
            continue
        print(f"\nProcessing {source_name}: {len(rows)} remaining chunks")

        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start:batch_start + BATCH_SIZE]
            texts = [r[2] for r in batch]

            for attempt in range(3):
                try:
                    embeddings = await get_embeddings(texts)
                    break
                except Exception as e:
                    print(f"  Retry {attempt+1}/3: {e}")
                    await asyncio.sleep(5)
            else:
                print(f"  FAILED batch, skipping")
                continue

            ids = []
            documents = []
            metadatas = []
            for row in batch:
                chunk_id, chunk_index, text, meta_json = row
                meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
                chroma_meta = {
                    "source": source_name,
                    "chunk_index": chunk_index,
                    "chunk_type": meta.get("chunk_type", "text"),
                    "original_filename": source_name,
                    "document_id": doc_id,
                }
                if "article_number" in meta:
                    chroma_meta["article_number"] = str(meta["article_number"])
                if "law" in meta:
                    chroma_meta["law"] = meta["law"]
                ids.append(str(chunk_id))
                documents.append(text)
                metadatas.append(chroma_meta)

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            done = min(batch_start + BATCH_SIZE, len(rows))
            print(f"  Indexed {done}/{len(rows)} chunks")

    print(f"\nChromaDB collection now has {collection.count()} chunks total")
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
