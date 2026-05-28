def normalize_memory_list(values, limit=10):
    """
    Deduplicate and bound memory limits
    """

    seen = set()
    normalized = []

    for item in reversed(values):
        if item not in seen:
            seen.add(item)
            normalized.append(item)
    normalized.reverse()
    return normalized[-limit:]