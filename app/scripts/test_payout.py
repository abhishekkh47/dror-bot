import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.llm.qa_pipeline import answer_query
from app.core.session_store import SessionStore
import asyncio

async def test():
    store = SessionStore()
    session = store.create_qa_session()
    
    query = "how will the vendor payout will be settled"
    print(f"Query: {query}")
    
    response = await answer_query(query, session.session_id, store)
    print(f"Mode: {response.mode}")
    print(f"Domain: {response.domain}")
    print(f"Confidence: {response.confidence}")
    print(f"Answer: {response.answer}")

if __name__ == "__main__":
    asyncio.run(test())
