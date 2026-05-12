from app.core.rag.retrieval_metadata import get_capability, get_lifecycle_stage, get_knowledge_type
INCLUDE_TRANSPORT_CONTEXT = False

def build_structured_context(context_chunks, operational_evidence, lifecycle_timeline):
    """
    Build a structured generation context for the LLM 
    from retrieved chunks and operational evidence
    """

    lifecycle_sections = []
    troubleshooting_sections = []
    transport_sections = []
    
    for idx, chunk in enumerate(context_chunks):
        metadata = chunk.get("metadata", {})
        lifecycle_stage = get_lifecycle_stage(chunk)
        knowledge_type = get_knowledge_type(chunk)

        content = chunk["context"]

        formatted = f"""
EVIDENCE_ID:
EV_{idx + 1:03d}

CAPABILITY:
{get_capability(chunk)}

LIFECYCLE_STAGE:
{lifecycle_stage}

KNOWLEDGE_TYPE:
{knowledge_type}

CONTENT:
{content}
""".strip()
        
        # Operational reasoning
        if knowledge_type in ["operational_behavior", "business_rule"]:
            lifecycle_sections.append(formatted)
        
        # Troubleshooting
        elif knowledge_type == "troubleshooting":
            troubleshooting_sections.append(formatted)
        
        # Transport
        elif knowledge_type == "transport_behavior":
            transport_sections.append(formatted)
        
    evidence_block = "\n".join([
        f"- {item}"
        for item in operational_evidence
    ])

    timeline_block = "\n".join([
        f"{idx + 1}. {event}"
        for idx, event in enumerate(
            lifecycle_timeline
        )
    ])

    sections = []

    sections.append(f"""
OPERATIONAL_EVIDENCE:
{evidence_block}
""".strip())

    sections.append(f"""
LIFECYCLE_TIMELINE:
{timeline_block}
""".strip())

    if lifecycle_sections:
        sections.append(f"""
LIFECYCLE_CONTEXT:

{chr(10).join(lifecycle_sections)}
""".strip())

    if troubleshooting_sections:
        sections.append(f"""
TROUBLESHOOTING_CONTEXT:

{chr(10).join(troubleshooting_sections)}
""".strip())

    if transport_sections and INCLUDE_TRANSPORT_CONTEXT:
        sections.append(f"""
TRANSPORT_CONTEXT:

{chr(10).join(transport_sections)}
""".strip())

    return "\n\n".join(sections)