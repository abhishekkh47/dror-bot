from app.core.rag.retrieval_metadata import get_capability, get_lifecycle_stage, get_knowledge_type

def build_structured_context(context_chunks, operational_evidence):
    """
    Build a structured generation context for the LLM 
    from retrieved chunks and operational evidence
    """

    lifecycle_sections = []
    troubleshooting_sections = []
    transport_sections = []
    
    for chunk in context_chunks:
        metadata = chunk.get("metadata", {})
        lifecycle_stage = get_lifecycle_stage(chunk)
        knowledge_type = get_knowledge_type(chunk)

        content = chunk["context"]

        formatted = f"""
CAPABILITY: {get_capability(chunk)}

LIFECYCLE_STAGE:
{lifecycle_stage}

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

    sections = []

    sections.append(f"""
OPERATIONAL_EVIDENCE:
{evidence_block}
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

    if transport_sections:
        sections.append(f"""
TRANSPORT_CONTEXT:

{chr(10).join(transport_sections)}
""".strip())

    return "\n\n".join(sections)