from rapidfuzz import fuzz


def validate_quote(
    quote: str,
    source: str,
    threshold: float = 85.0
) -> tuple[bool, float]:
    """
    Validates whether an extracted verbatim AI quote matches
    the original raw source material. (Fix 1)

    Returns:
        tuple: (passes_validation_bool, calculated_similarity_score_float)
    """
    if not quote or not source:
        return False, 0.0

    # Execute partial ratio similarity check across variant segments
    score = fuzz.partial_ratio(quote.lower(), source.lower())
    passes = score >= threshold

    return passes, float(score)
