from typing import List, Optional, Tuple

from app.schemas import ExtractionResult
from app.validate import ValidationResult


def route(
    extraction: ExtractionResult,
    validation: ValidationResult,
    auto_limit: float,
    min_confidence: float,
    flags: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """Return ("auto" | "review", reasons). ClaimPilot never auto-rejects; a human decides."""
    reasons = list(validation.issues) + list(flags or [])
    if extraction.confidence < min_confidence:
        reasons.append("low extraction confidence ({:.2f})".format(extraction.confidence))
    amount = extraction.claim.estimated_amount
    if amount is not None and amount > auto_limit:
        reasons.append("amount above auto-submit limit ({:,.0f})".format(auto_limit))
    # The model lists an ambiguity on almost every email (80/80 in evals), so its notes inform the reviewer
    # but don't block. Deterministic checks above decide.
    advisory = [n for n in extraction.notes if n.startswith("model: ")]
    reasons.extend(n for n in extraction.notes if not n.startswith("model: "))
    return ("review" if reasons else "auto"), reasons + advisory
