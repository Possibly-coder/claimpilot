from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.schemas import REQUIRED_FIELDS, ExtractedClaim, ExtractionResult


class Extractor:
    name = "base"

    def extract(self, text: str, locale: Optional[str] = None) -> ExtractionResult:
        raise NotImplementedError


def completeness(claim: ExtractedClaim) -> float:
    found = sum(1 for f in REQUIRED_FIELDS if getattr(claim, f) is not None)
    return found / len(REQUIRED_FIELDS)


def safe_claim(data: Dict[str, Any]) -> Tuple[ExtractedClaim, List[str]]:
    """Build a claim field by field so one malformed value doesn't drop the rest."""
    clean: Dict[str, Any] = {}
    notes: List[str] = []
    for field in ExtractedClaim.model_fields:
        value = data.get(field)
        if value is None:
            continue
        try:
            ExtractedClaim(**{field: value})
            clean[field] = value
        except ValidationError:
            notes.append("dropped invalid {}: {!r}".format(field, value))
    return ExtractedClaim(**clean), notes
