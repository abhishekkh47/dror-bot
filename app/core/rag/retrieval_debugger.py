def print_retrieval_trace(trace):
    print("\n=== RETRIEVAL TRACE ===")

    for decision in trace.decisions:
        print(
            f"""
            Chunk: {decision.chunk_id}
            Included: {decision.included}
            Capability: {decision.capability}
            Stage: {decision.lifecycle_stage}
            Type: {decision.knowledge_type}

            Base Score: {decision.base_score:.4f}
            Adjusted Score: {decision.adjusted_score:.4f}

            Breakdown:
            {decision.score_breakdown}

            Exclusion:
            {decision.exclusion_reason}
            """
        )