from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class LossType(str, Enum):
    auto_collision = "auto_collision"
    auto_theft = "auto_theft"
    property_water = "property_water"
    property_fire = "property_fire"
    other = "other"


class ExtractedClaim(BaseModel):
    policy_number: Optional[str] = None
    claimant_name: Optional[str] = None
    incident_date: Optional[date] = None
    loss_type: Optional[LossType] = None
    estimated_amount: Optional[float] = None
    description: Optional[str] = None


REQUIRED_FIELDS = ["policy_number", "claimant_name", "incident_date", "loss_type", "estimated_amount"]


class ExtractionResult(BaseModel):
    claim: ExtractedClaim
    confidence: float
    extractor: str
    latency_ms: float
    cost_usd: float = 0.0
    notes: List[str] = []


class IntakeRequest(BaseModel):
    sender: str
    subject: str = ""
    body: str


class ClaimOut(BaseModel):
    id: int
    sender: str
    subject: str
    raw_text: str
    extracted: ExtractedClaim
    confidence: float
    extractor: str
    latency_ms: float
    cost_usd: float
    status: str
    reasons: List[str]
    legacy_ref: Optional[str]


class ApproveRequest(BaseModel):
    corrections: Optional[ExtractedClaim] = None
