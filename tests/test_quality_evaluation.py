"""
LegalRAG Quality Evaluation — 12 Questions Test Suite
Tests the system with questions about the Consumer Protection Law.
"""

import httpx
import json
import time
import sys

API_BASE = "http://localhost:8080"

QUESTIONS = [
    # Definition questions
    {
        "id": 1,
        "query": "Какие обязательства по качеству товара имеет продавец согласно закону о защите прав потребителей?",
        "type": "definition",
        "expected_keywords": ["качеств", "договор", "продавец", "потребител"],
        "expected_articles": ["4"],
    },
    # Rights questions
    {
        "id": 2,
        "query": "Какие права имеет потребитель при обнаружении недостатков товара?",
        "type": "rights",
        "expected_keywords": ["замен", "возврат", "недостат", "потребител"],
        "expected_articles": ["18"],
    },
    # Timeline/deadline questions
    {
        "id": 3,
        "query": "В какой срок продавец обязан удовлетворить требования потребителя о возврате денег?",
        "type": "deadline",
        "expected_keywords": ["десят", "10", "дней", "требован"],
        "expected_articles": ["22"],
    },
    {
        "id": 4,
        "query": "В течение какого срока потребитель может обменять товар надлежащего качества?",
        "type": "deadline",
        "expected_keywords": ["четырнадцат", "14", "дней", "обмен"],
        "expected_articles": ["25"],
    },
    # Procedural questions
    {
        "id": 5,
        "query": "Какой порядок обмена непродовольственного товара надлежащего качества?",
        "type": "procedure",
        "expected_keywords": ["обмен", "товарн", "вид", "чек", "употреблен"],
        "expected_articles": ["25"],
    },
    # Penalty questions
    {
        "id": 6,
        "query": "Какая неустойка предусмотрена за просрочку выполнения требований потребителя?",
        "type": "penalty",
        "expected_keywords": ["процент", "1%", "неустойк", "день", "просрочк"],
        "expected_articles": ["23"],
    },
    # Comparison/analysis questions
    {
        "id": 7,
        "query": "Сравните права потребителя при обнаружении недостатков товара и при обнаружении недостатков работы (услуги)",
        "type": "comparison",
        "expected_keywords": ["товар", "работ", "услуг", "недостат"],
        "expected_articles": ["18", "29"],
    },
    # Seasonal goods
    {
        "id": 8,
        "query": "Как исчисляется гарантийный срок для сезонных товаров?",
        "type": "specific",
        "expected_keywords": ["сезон", "обув", "одежд", "климат"],
        "expected_articles": ["19"],
    },
    # Warranty period absence
    {
        "id": 9,
        "query": "Что делать, если на товар не установлен гарантийный срок?",
        "type": "procedure",
        "expected_keywords": ["два", "год", "2", "разумн", "срок"],
        "expected_articles": ["19"],
    },
    # Rights to manufacturer
    {
        "id": 10,
        "query": "Может ли потребитель предъявить требования непосредственно изготовителю товара?",
        "type": "rights",
        "expected_keywords": ["изготовител", "импорт", "требован"],
        "expected_articles": ["18"],
    },
    # Real estate
    {
        "id": 11,
        "query": "В течение какого срока можно предъявить претензии по недостаткам строительных работ?",
        "type": "deadline",
        "expected_keywords": ["пят", "5", "лет", "недвижим", "строен"],
        "expected_articles": ["29"],
    },
    # Substantial defects
    {
        "id": 12,
        "query": "В каких случаях потребитель может отказаться от договора на выполнение работы?",
        "type": "rights",
        "expected_keywords": ["отказ", "договор", "существен", "недостат", "срок"],
        "expected_articles": ["29"],
    },
]


def test_question(q: dict) -> dict:
    """Send a question and evaluate the response."""
    start = time.time()
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{API_BASE}/api/query",
                json={"query": q["query"], "max_results": 10, "use_cache": False},
            )
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {**q, "status": "ERROR", "elapsed": elapsed, "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        answer = data.get("answer", "")
        sources = data.get("sources", data.get("source_documents", []))
        chunks = data.get("chunks_used", len(sources))
        confidence = data.get("confidence", 0)

        # Evaluate keyword coverage
        answer_lower = answer.lower()
        found_keywords = [kw for kw in q["expected_keywords"] if kw.lower() in answer_lower]
        keyword_score = len(found_keywords) / len(q["expected_keywords"]) if q["expected_keywords"] else 1.0

        # Evaluate article citation
        found_articles = []
        for art in q["expected_articles"]:
            if art in answer or f"ст. {art}" in answer or f"статья {art}" in answer.lower() or f"статьи {art}" in answer.lower() or f"статьёй {art}" in answer.lower():
                found_articles.append(art)
        article_score = len(found_articles) / len(q["expected_articles"]) if q["expected_articles"] else 1.0

        # Overall quality score
        has_answer = len(answer) > 50
        quality = (
            (0.4 * keyword_score) +
            (0.3 * article_score) +
            (0.2 * (1.0 if has_answer else 0.0)) +
            (0.1 * min(confidence, 1.0))
        )

        return {
            **q,
            "status": "OK",
            "elapsed": elapsed,
            "answer_len": len(answer),
            "chunks": chunks,
            "confidence": confidence,
            "keyword_score": keyword_score,
            "article_score": article_score,
            "quality": quality,
            "found_keywords": found_keywords,
            "found_articles": found_articles,
            "answer_preview": answer[:200],
        }
    except Exception as e:
        return {**q, "status": "ERROR", "elapsed": time.time() - start, "error": str(e)}


def main():
    print("=" * 80)
    print("LegalRAG Quality Evaluation — 12 Questions")
    print("Document: Zakon o zashite prav potrebitelej (Consumer Protection)")
    print("=" * 80)
    print()

    results = []
    total_ok = 0
    total_quality = 0.0

    for q in QUESTIONS:
        print(f"[Q{q['id']:02d}] {q['query'][:70]}...")
        result = test_question(q)
        results.append(result)

        if result["status"] == "OK":
            total_ok += 1
            total_quality += result["quality"]
            kw_pct = f"{result['keyword_score']:.0%}"
            art_pct = f"{result['article_score']:.0%}"
            print(f"  -> OK | {result['elapsed']:.1f}s | {result['answer_len']} chars | "
                  f"chunks={result['chunks']} | keywords={kw_pct} | articles={art_pct} | "
                  f"quality={result['quality']:.0%}")
        else:
            print(f"  -> ERROR: {result.get('error', 'unknown')}")
        print()

    print("=" * 80)
    print("SUMMARY")
    print(f"  Answered: {total_ok}/{len(QUESTIONS)}")
    avg_q = total_quality / total_ok if total_ok else 0
    print(f"  Avg quality: {avg_q:.0%}")
    avg_time = sum(r.get("elapsed", 0) for r in results) / len(results) if results else 0
    print(f"  Avg time: {avg_time:.1f}s")

    good = sum(1 for r in results if r.get("quality", 0) >= 0.6)
    print(f"  Good answers (>=60%): {good}/{len(QUESTIONS)}")
    print("=" * 80)

    # Detailed results
    print("\nDETAILED RESULTS:")
    for r in results:
        q_id = r["id"]
        status = r["status"]
        if status == "OK":
            print(f"\n  Q{q_id}: quality={r['quality']:.0%}")
            print(f"    Keywords found: {r['found_keywords']}")
            print(f"    Articles cited: {r['found_articles']}")
            print(f"    Preview: {r['answer_preview'][:150]}...")
        else:
            print(f"\n  Q{q_id}: {status} - {r.get('error', '')}")

    return 0 if good >= 8 else 1


if __name__ == "__main__":
    sys.exit(main())
