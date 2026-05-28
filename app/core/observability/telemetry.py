def build_telemetry_event(
    execution_result,
    query,
    step,
    total_latency_ms,
    cache_hit=False,
):
    """
    Build orchestration telemetry event.
    """

    return {
        "query": query,

        "step_id": step.id,

        "rag_topic": step.rag_topic,

        "cache_hit": cache_hit,

        "retrieval_confidence":
            execution_result.retrieval_confidence,

        "response_mode":
            execution_result.response_mode,

        "quality_score":
            execution_result.quality_score,

        "retrieval_stability_score":
            execution_result.retrieval_stability_score,

        "lifecycle_coherence_score":
            execution_result.lifecycle_coherence_score,

        "response_reliability_score":
            execution_result.response_reliability_score,

        "retry_attempted":
            execution_result.retry_attempted,

        "reasoning_issue_count":
            len(
                execution_result.reasoning_issues
            ),

        "operational_conflict_count":
            len(
                execution_result.operational_conflicts
            ),

        "operational_ambiguity_count":
            len(
                execution_result.operational_ambiguities
            ),

        "selected_chunk_count":
            len(
                execution_result.selected_chunks
            ),

        "human_escalation_required":
            execution_result.human_escalation_required,

        "latency_ms":
            total_latency_ms,
    }
