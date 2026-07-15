import sys
import os
sys.path.append(os.path.abspath("."))
from app.core.llm.retriever import store
import pprint
res = store.search("how to add a new user to my platform", top_k=3)
pprint.pprint(res)
