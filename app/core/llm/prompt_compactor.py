from app.core.llm.prompt_budget import (
    MAX_CONTEXT_CHUNKS,
    MAX_OPERATIONAL_EVIDENCE,
    MAX_MEMORY_FINDINGS,
)


def compact_prompt_inputs(
    distilled_chunks,
    operational_evidence,
    memory_summary,
):
    """
    Compact prompt inputs
    into bounded signal-focused context.
    """

    compacted_chunks = distilled_chunks[:MAX_CONTEXT_CHUNKS]

    compacted_evidence = operational_evidence[:MAX_OPERATIONAL_EVIDENCE]

    compacted_memory = {
        "active_lifecycle_states":
            memory_summary.get(
                "active_lifecycle_states",
                []
            )[:3],

        "major_operational_findings":
            memory_summary.get(
                "major_operational_findings",
                []
            )[:MAX_MEMORY_FINDINGS],

        "active_topics":
            memory_summary.get(
                "active_topics",
                []
            )[:3],
    }

    return {
        "distilled_chunks": compacted_chunks,
        "operational_evidence": compacted_evidence,
        "memory_summary": compacted_memory,
    }