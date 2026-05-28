import hashlib


def build_response_cache_key(
    query,
    step,
):
    """
    Build deterministic response cache key.
    """

    raw = (
        f"{query}|"
        f"{step.id}|"
        f"{step.rag_topic}"
    )

    hashed = hashlib.md5(
        raw.encode()
    ).hexdigest()

    return f"drorbot:response:{hashed}"