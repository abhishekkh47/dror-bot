import re
from typing import List, Tuple
from app.utils.patterns import NOISE_PATTERNS

def clean_operational_text(text: str) -> str:
    """
    Remove implementation-heavy operational noise
    while preserving lifecycle meaning.
    """

    lines = text.splitlines()
    cleaned = []

    for line in lines: 
        stripped = line.strip()
        if not stripped:
            continue

        should_skip = False

        for pattern in NOISE_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                should_skip = True
                break
        if not should_skip:
            cleaned.append(stripped)
        
        return "\n".join(cleaned)

def distill_chunks(filtered_chunks: List[Tuple[float, dict]]):
    """
    Distill retrieved chunks into operationally relevant evidence
    """

    distilled_chunks = []
    for _, chunk in filtered_chunks:
        cleaned_chunk = clean_operational_text(chunk["content"])

        distilled_chunks.append({
            "topic": chunk["topic"],
            "tags": chunk.get("tags", []),
            "content": cleaned_chunk
        })
        return distilled_chunks