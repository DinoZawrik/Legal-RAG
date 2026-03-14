"""Load demo legal documents into ChromaDB for testing."""
import asyncio
import sys
import os
import uuid
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

async def main():
    from core.vector_store_manager import VectorStoreManager
    from core.infrastructure_suite import TextChunk

    # Initialize vector store
    vs = VectorStoreManager()
    ok = await vs.initialize()
    if not ok:
        print("FAILED to initialize vector store")
        return

    # Read demo documents
    demo_dir = os.path.join(os.getcwd(), "demo_documents")
    chunks = []

    for fname in os.listdir(demo_dir):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(demo_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()

        # Split into chunks by articles (Статья)
        import re
        articles = re.split(r'(?=Статья \d+)', text)

        doc_name = fname.replace(".txt", "")
        for i, article_text in enumerate(articles):
            article_text = article_text.strip()
            if len(article_text) < 50:
                continue

            # Extract article number if present
            art_match = re.match(r'Статья (\d+)', article_text)
            art_num = art_match.group(1) if art_match else str(i)

            chunk = TextChunk(
                id=f"{doc_name}::article-{art_num}",
                text=article_text,
                metadata={
                    "source": fname,
                    "document_type": "federal_law",
                    "article_number": art_num,
                    "law": doc_name.replace("_", " ").title(),
                    "chunk_type": "legal_article",
                }
            )
            chunks.append(chunk)

    print(f"Prepared {len(chunks)} chunks from {len(os.listdir(demo_dir))} files")

    # Upload to ChromaDB
    success = await vs.add_documents(chunks)
    print(f"Upload success: {success}")

    # Verify
    count = await vs.collection.count()
    print(f"Total documents in ChromaDB: {count}")

    # Test search
    results = await vs.search_similar("трудовой договор", limit=3)
    print(f"\nTest search 'трудовой договор': {len(results)} results")
    for i, r in enumerate(results):
        text_preview = r.get("text", r.get("document", ""))[:100]
        print(f"  {i+1}. {text_preview}...")

asyncio.run(main())
