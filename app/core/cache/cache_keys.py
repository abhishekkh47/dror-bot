import hashlib


def build_response_cache_key(
    query: str,
    history_text: str,
):
    """
    Build deterministic response cache key for QA pipeline.
    """

    raw = (
        f"{query}|"
        f"{history_text}"
    )

    hashed = hashlib.md5(
        raw.encode()
    ).hexdigest()

    return f"drorbot:response:{hashed}"