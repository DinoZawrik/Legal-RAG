#!/usr/bin/env python3
"""Utility to run the RAG workflow against a subset of regression questions."""

import asyncio
from typing import Sequence

from core.langgraph_rag_workflow import LangGraphRAGWorkflow


QUESTIONS: Sequence[str] = (
    "Какие расходы могут быть возмещены концессионеру в случае досрочного прекращения концессионного соглашения?",
    "Что такое плата концедента?",
    "Какая статья закона о концессионных соглашениях регулирует финансовое участие концедента?",
    "Что такое иное передаваемое концедентом имущество по концессионному соглашению?",
    "Что регулирует соглашение, заключаемое концедентом, концессионером и кредитором?",
)


async def main() -> None:
    workflow = LangGraphRAGWorkflow()

    for index, question in enumerate(QUESTIONS, start=1):
        print("=" * 80)
        print(f"ВОПРОС {index}/{len(QUESTIONS)}")
        print("=" * 80)
        print(question)

        try:
            result = await workflow.run(question)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ ОШИБКА: {exc}\n")
            continue

        answer = (result.get("answer") or "").strip()
        confidence = result.get("confidence", 0.0)

        print("✅ ОТВЕТ:\n")
        print(answer or "(Ответ пустой)")
        print(f"\nУверенность: {confidence:.2f}\n")


if __name__ == "__main__":
    asyncio.run(main())


