def get_metadata(chunk):
    return chunk.get("metadata", {})


def get_business_domain(chunk):
    return get_metadata(chunk).get(
        "business_domain"
    )


def get_capability(chunk):
    return get_metadata(chunk).get(
        "capability"
    )


def get_lifecycle_stage(chunk):
    return get_metadata(chunk).get(
        "lifecycle_stage"
    )


def get_knowledge_type(chunk):
    return get_metadata(chunk).get(
        "knowledge_type"
    )


def get_mechanism(chunk):
    return get_metadata(chunk).get(
        "mechanism"
    )


def get_visibility(chunk):
    return get_metadata(chunk).get(
        "visibility"
    )


def get_importance(chunk):
    return get_metadata(chunk).get(
        "importance"
    )