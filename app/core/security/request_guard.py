BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "reveal system prompt",
    "show hidden prompt",
    "bypass restrictions",
    "override instructions",
]

MAX_QUERY_LENGTH = 2000


def validate_request(query):
    """
    Validate incoming request safety.
    """

    if len(query) > MAX_QUERY_LENGTH:
        return False, "Query too large"

    query_lower = query.lower()

    for pattern in BLOCKED_PATTERNS:

        if pattern in query_lower:

            return False, "Unsafe request pattern detected"

    return True, None