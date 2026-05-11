from typing import List

def validate_retrieval_quality(selected_chunks, lifecycle_facts):
    """
    Validate whether the retrieval evidence
    is operationally sufficient for generation
    """

    if not selected_chunks:
        return False, "no_selected_chunks"

    # Require minimum evidence count
    if len(selected_chunks) < 2:
        return False, "insufficient_chunk_count"

    metadata_list = [
        chunk.get("metadata", {})
        for _, chunk in selected_chunks
    ]

    lifecycle_stages = {
        m.get("lifecycle_stage")
        for m in metadata_list
    }
    
    knowledge_types = {
        m.get("knowledge_type")
        for m in metadata_list
    }

    # Require operational lifecycle evidence
    if (lifecycle_facts.transaction_cancelled and "cancellation" not in lifecycle_stages):
        return False, "missing_cancellation_evidence"
    
    # Require operational reasoning chunks
    operational_type = {
        "operational_behavior",
        "troubleshooting",
        "business_rule",
    }

    if not any(
        k in operational_type
        for k in knowledge_types
    ):
        return False, "missing_operational_evidence"
    
    return True, None