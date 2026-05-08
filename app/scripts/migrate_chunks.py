import json
import uuid

from app.core.rag.chunk_schema import (
    RAGChunk,
    ChunkMetadata,
)


def infer_metadata(chunk):
    """
    Infer canonical metadata from legacy chunk structure.
    """

    topic = chunk.get("topic", "").lower()

    tags = chunk.get("tags", [])

    # Default values
    business_domain = "payments"

    capability = "general"

    lifecycle_stage = "general"

    knowledge_type = "operational_behavior"

    artifact_type = "explanation"

    mechanism = None

    importance = "medium"

    # Capability inference
    if "intent" in topic:
        capability = "create_intent"

    elif "transaction" in topic:
        capability = "platform_transaction"

    elif "completion" in topic:
        capability = "auto_completion"

    # Lifecycle inference
    if "validation" in topic:
        lifecycle_stage = "validation"

    elif "completion" in topic:
        lifecycle_stage = "auto_completion"

    elif "cancel" in topic:
        lifecycle_stage = "cancellation"

    # Mechanism inference
    if "webhook" in tags:
        mechanism = "webhook"

    elif "socket" in tags:
        mechanism = "socket"

    elif "polling" in tags:
        mechanism = "polling"

    # Knowledge type inference
    if mechanism:
        knowledge_type = "transport_behavior"

    # Importance inference
    if any(tag in tags for tag in [
        "failure",
        "rollback",
        "cancellation",
    ]):
        importance = "high"

    return ChunkMetadata(
        business_domain=business_domain,
        capability=capability,
        lifecycle_stage=lifecycle_stage,
        knowledge_type=knowledge_type,
        artifact_type=artifact_type,
        mechanism=mechanism,
        importance=importance,
    )


def migrate_chunks(input_file, output_file):
    with open(input_file, "r") as f:
        old_chunks = json.load(f)

    migrated = []

    for chunk in old_chunks:
        metadata = infer_metadata(chunk)

        migrated_chunk = RAGChunk(
            id=str(uuid.uuid4()),

            metadata=metadata,

            tags=chunk.get("tags", []),

            content=chunk["content"],
        )

        migrated.append(
            migrated_chunk.model_dump()
        )

    with open(output_file, "w") as f:
        json.dump(migrated, f, indent=2)

    print(f"Migrated {len(migrated)} chunks.")

if __name__ == "__main__":
    migrate_chunks(
        input_file="app/data/rag/rag_chunks_create_intent.json",
        output_file="app/data/rag/rag_chunks_v2.json",
    )