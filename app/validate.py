from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Policy
from app.schemas import REQUIRED_FIELDS, ExtractedClaim


@dataclass
class ValidationResult:
    issues: List[str] = field(default_factory=list)
    policy: Optional[Policy] = None

    @property
    def ok(self) -> bool:
        return not self.issues


def _norm_name(name: str) -> str:
    return " ".join(name.lower().split())


def validate_claim(db: Session, claim: ExtractedClaim, today: Optional[date] = None) -> ValidationResult:
    today = today or date.today()
    result = ValidationResult()

    for f in REQUIRED_FIELDS:
        if getattr(claim, f) is None:
            result.issues.append("missing {}".format(f))

    if claim.policy_number:
        result.policy = db.scalar(select(Policy).where(Policy.policy_number == claim.policy_number))
        if result.policy is None:
            result.issues.append("policy {} not found".format(claim.policy_number))

    policy = result.policy
    if claim.incident_date:
        if claim.incident_date > today:
            result.issues.append("incident date is in the future")
        if policy and not (policy.start_date <= claim.incident_date <= policy.end_date):
            result.issues.append("incident date outside policy period")

    if policy and claim.loss_type and claim.loss_type.value not in policy.covered():
        result.issues.append("loss type {} not covered by policy".format(claim.loss_type.value))

    if claim.estimated_amount is not None:
        if claim.estimated_amount <= 0:
            result.issues.append("estimated amount must be positive")
        elif policy and claim.estimated_amount > policy.coverage_limit:
            result.issues.append("amount exceeds coverage limit")

    if policy and claim.claimant_name and _norm_name(claim.claimant_name) != _norm_name(policy.holder_name):
        result.issues.append("claimant name does not match policy holder")

    return result
