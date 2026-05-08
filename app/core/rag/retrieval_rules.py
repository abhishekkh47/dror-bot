NOISE_TOPICS = [
    "create_intent_pending_event_without_completion"
]

def is_noise_chunk(chunk):
    return chunk.get("topic", "") in NOISE_TOPICS
