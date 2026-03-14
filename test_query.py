"""Quick test of the full RAG query pipeline."""
import httpx
import json
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            'http://localhost:8080/api/query',
            json={'query': 'Что такое трудовой договор?', 'max_results': 5}
        )
        print(f'Status: {resp.status_code}')
        if resp.status_code == 200:
            data = resp.json()
            success = data.get('success')
            answer = data.get('answer', '')
            chunks = data.get('chunks_used')
            model = data.get('metadata', {}).get('model_used')
            print(f'Success: {success}')
            print(f'Chunks: {chunks}')
            print(f'Model: {model}')
            print(f'Answer ({len(answer)} chars):')
            print(answer[:500])
            
            sources = data.get('sources', [])
            print(f'\nSources: {len(sources)}')
            for i, s in enumerate(sources[:3], 1):
                if isinstance(s, dict):
                    meta = s.get('metadata', {})
                    law = meta.get('law', meta.get('law_number', ''))
                    text = (s.get('text', '') or '')[:100]
                    print(f'  {i}. {law}: {text}...')
        else:
            print(f'Error: {resp.text[:500]}')

asyncio.run(test())
