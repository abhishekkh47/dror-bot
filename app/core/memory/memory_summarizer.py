def summarize_investigation_state(session_memory):
    """
    Compress operational investigation state
    """

    summary = {
        "active_lifecycle_states": [],
        "major_operational_findings": [],
        "active_topics": [],
    }

    lifecycle_facts = session_memory.lifecycle_facts

    # Active lifecycle states
    for key, value in lifecycle_facts.items():
        if value is True:
            summary["active_lifecycle_states"].append(key)
    
    # Operational findings
    findings = session_memory.inferred_conclusions[-5:]
    summary["major_operational_findings"] = findings

    # Active topics
    unique_topics = list(set(
        session_memory.discussed_topics
    ))

    summary["active_topics"] = unique_topics

    return summary