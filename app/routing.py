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
    reasons.extend(extraction.notes)
    return ("review" if reasons else "auto"), reasons
