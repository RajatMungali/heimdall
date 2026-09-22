from typing import Optional
from backend.config import settings


def apply_icp_filters(
    base_score: float,
    employee_count: Optional[int],
    funding_stage: Optional[str],
    industry: str
) -> tuple[int, str]:
    """
    Evaluates firmographic vectors to calculate hard ceiling caps and
    deduction scoring modifications. (Fix 3)
    """
    score = base_score
    fit_label = "Strong"
    penalties = 0

    from backend.config_manager import load_intent_config
    _config = load_intent_config()
    active_niche = _config.get("active_niche", "recruitment")
    niche_info = _config.get("niches", {}).get(active_niche, {})

    min_hc = niche_info.get("min_employees", 20)
    max_hc = niche_info.get("max_employees", 2000)

    # 1. Scale Constraints: Capacity Check
    if employee_count is not None:
        if isinstance(employee_count, str):
            import re
            # Extract the upper bound of the estimate (e.g., "50-200" -> 200)
            matches = re.findall(r'\d+', employee_count.replace(',', ''))
            if matches:
                # If range, take max. If single number, take it.
                parsed_count = max(int(m) for m in matches)
            else:
                parsed_count = 100  # Default safe assumption
        else:
            parsed_count = employee_count
            
        if parsed_count > max_hc:
            score = min(score, 35)  # Enterprise internal sales block cap
            fit_label = "Poor"
        elif parsed_count < min_hc:
            score = min(score, 35)  # Under-resourced/pre-revenue block cap
            fit_label = "Poor"

    # 2. Maturity Level Analysis (exact match — audit fix)
    if funding_stage:
        stagnant_stages = ["Series D", "Series E", "Public", "M&A"]
        if any(funding_stage.lower() == stage.lower() for stage in stagnant_stages):
            score = min(score, 30)  # Locked internal operations block cap
            fit_label = "Poor"

    # 3. Industry Vertical Alignment (reads from active niche in intent_config.json)
    target_list = niche_info.get("target_industries") or _config.get("target_industries", settings.ICP.TARGET_INDUSTRIES)
    if not any(tgt.lower() in industry.lower() for tgt in target_list):
        penalties += 10  # Out of sector mismatch deduction
        if fit_label != "Poor":
            fit_label = "Partial"

    # Apply all accumulated penalties
    score -= penalties

    # Enforce standard scoring boundaries
    final_score = max(0, min(int(score), 100))
    return final_score, fit_label
