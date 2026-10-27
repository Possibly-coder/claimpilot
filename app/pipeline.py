import json
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import Settings
from app.documents import infer_locale
from app.extract.base import Extractor
from app.guards import ambiguity_flags
from app.legacy_client import LegacyClaimsClient, LegacyWriteError
from app.models import Claim
from app.routing import route
from app.schemas import ExtractedClaim, ExtractionResult
from app.validate import validate_claim


def _reasons(claim: Claim) -> List[str]:
    return json.loads(claim.reasons_json or "[]")


def submit_to_legacy(
    db: Session, claim: Claim, legacy: Optional[LegacyClaimsClient], success_status: str
) -> Claim:
    if legacy is None:
        claim.status = success_status
    else:
        extracted = ExtractedClaim.model_validate_json(claim.extracted_json)
        try:
            claim.legacy_ref = legacy.submit(claim.id, extracted)
            claim.status = success_status
        except LegacyWriteError as exc:
            claim.status = "writeback_failed"
            claim.reasons_json = json.dumps(_reasons(claim) + ["write-back failed: {}".format(exc)])
    db.commit()
    return claim


def process_intake(
    db: Session,
    sender: str,
    subject: str,
    text: str,
    extractor: Extractor,
    legacy: Optional[LegacyClaimsClient],
    cfg: Settings,
) -> Claim:
    locale = infer_locale(sender)
    try:
        result = extractor.extract(text, locale)
    except Exception as exc:  # model/API outages must not lose the claim
        result = ExtractionResult(
            claim=ExtractedClaim(), confidence=0.0, extractor=extractor.name,
            latency_ms=0.0, notes=["extraction failed: {}".format(exc)],
        )

    validation = validate_claim(db, result.claim)
    decision, reasons = route(
        result, validation, cfg.auto_approve_limit, cfg.min_confidence, flags=ambiguity_flags(text)
    )

    claim = Claim(
        sender=sender,
        subject=subject,
        raw_text=text,
        extracted_json=result.claim.model_dump_json(),
        confidence=result.confidence,
        extractor=result.extractor,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        status="needs_review",
        reasons_json=json.dumps(reasons),
    )
    db.add(claim)
    db.commit()

    if decision == "auto":
        submit_to_legacy(db, claim, legacy, success_status="auto_submitted")
    return claim


def approve(
    db: Session, claim: Claim, corrections: Optional[ExtractedClaim], legacy: Optional[LegacyClaimsClient]
) -> Claim:
    if corrections is not None:
        current = ExtractedClaim.model_validate_json(claim.extracted_json)
        merged = current.model_copy(update=corrections.model_dump(exclude_none=True))
        claim.extracted_json = merged.model_dump_json()
    return submit_to_legacy(db, claim, legacy, success_status="approved")
