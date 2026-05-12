def build_confidence_policy(
    retrieval_confidence,
):
    """
    Build response behavior policy
    based on retrieval confidence.
    """

    if retrieval_confidence >= 0.75:
        return {
            "tone": "confident",
            "allow_causal_reasoning": True,
            "allow_operational_conclusions": True,
            "require_uncertainty_language": False,
        }

    elif retrieval_confidence >= 0.45:
        return {
            "tone": "moderate",
            "allow_causal_reasoning": True,
            "allow_operational_conclusions": True,
            "require_uncertainty_language": True,
        }

    else:
        return {
            "tone": "cautious",
            "allow_causal_reasoning": False,
            "allow_operational_conclusions": False,
            "require_uncertainty_language": True,
        }