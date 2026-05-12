def build_execution_metrics(
    result,
):
    """
    Build structured execution metrics
    from pipeline execution result.
    """

    return {
        "quality_score":
            result.quality_score,

        "retrieval_confidence":
            result.retrieval_confidence,

        "response_mode":
            result.response_mode,

        "reasoning_issue_count":
            len(result.reasoning_issues),

        "has_reasoning_issues":
            len(result.reasoning_issues) > 0,
    }