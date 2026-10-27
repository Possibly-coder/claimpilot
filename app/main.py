import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import pipeline
from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.documents import pdf_to_text
from app.extract import get_extractor
from app.extract.base import Extractor
from app.legacy_client import LegacyClaimsClient
from app.models import Claim
from app.schemas import ApproveRequest, ClaimOut, ExtractedClaim, IntakeRequest
from app.seed_data import seed_policies

STATIC = Path(__file__).parent / "static"

_extractor: Optional[Extractor] = None
_legacy: Optional[LegacyClaimsClient] = None


def get_extractor_dep() -> Extractor:
    global _extractor
    if _extractor is None:
        _extractor = get_extractor(settings)
    return _extractor


def get_legacy_dep() -> Optional[LegacyClaimsClient]:
    global _legacy
    if _legacy is None and settings.legacy_api_url:
        _legacy = LegacyClaimsClient(settings.legacy_api_url)
    return _legacy


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        seed_policies(db)
    finally:
        db.close()
    yield


app = FastAPI(title="ClaimPilot", version="0.1.0", lifespan=lifespan)


def claim_out(claim: Claim) -> ClaimOut:
    return ClaimOut(
        id=claim.id,
        sender=claim.sender,
        subject=claim.subject,
        raw_text=claim.raw_text,
        extracted=ExtractedClaim.model_validate_json(claim.extracted_json),
        confidence=claim.confidence,
        extractor=claim.extractor,
        latency_ms=claim.latency_ms,
        cost_usd=claim.cost_usd,
        status=claim.status,
        reasons=json.loads(claim.reasons_json or "[]"),
        legacy_ref=claim.legacy_ref,
    )


def _get_claim(db: Session, claim_id: int) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    return claim


@app.get("/")
def review_ui() -> FileResponse:
    return FileResponse(STATIC / "review.html")


@app.get("/health")
def health(extractor: Extractor = Depends(get_extractor_dep)) -> dict:
    return {"status": "ok", "extractor": extractor.name, "legacy_writeback": bool(settings.legacy_api_url)}


@app.post("/claims/intake", response_model=ClaimOut)
def intake(
    req: IntakeRequest,
    db: Session = Depends(get_db),
    extractor: Extractor = Depends(get_extractor_dep),
    legacy: Optional[LegacyClaimsClient] = Depends(get_legacy_dep),
) -> ClaimOut:
    claim = pipeline.process_intake(db, req.sender, req.subject, req.body, extractor, legacy, settings)
    return claim_out(claim)


@app.post("/claims/intake/upload", response_model=ClaimOut)
async def intake_upload(
    sender: str = Form(...),
    subject: str = Form(""),
    body: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    extractor: Extractor = Depends(get_extractor_dep),
    legacy: Optional[LegacyClaimsClient] = Depends(get_legacy_dep),
) -> ClaimOut:
    data = await file.read()
    name = file.filename or "attachment"
    if name.lower().endswith(".pdf") or file.content_type == "application/pdf":
        attachment_text = pdf_to_text(data)
    elif (file.content_type or "").startswith("text/") or name.lower().endswith(".txt"):
        attachment_text = data.decode("utf-8", errors="replace")
    else:
        raise HTTPException(415, "only PDF and text attachments are supported")
    text = "{}\n\n[Attachment: {}]\n{}".format(body, name, attachment_text).strip()
    claim = pipeline.process_intake(db, sender, subject, text, extractor, legacy, settings)
    return claim_out(claim)


@app.get("/claims", response_model=List[ClaimOut])
def list_claims(status: Optional[str] = None, db: Session = Depends(get_db)) -> List[ClaimOut]:
    query = select(Claim).order_by(Claim.id.desc()).limit(200)
    if status:
        query = query.where(Claim.status == status)
    return [claim_out(c) for c in db.scalars(query)]


@app.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: int, db: Session = Depends(get_db)) -> ClaimOut:
    return claim_out(_get_claim(db, claim_id))


@app.post("/claims/{claim_id}/approve", response_model=ClaimOut)
def approve_claim(
    claim_id: int,
    req: ApproveRequest,
    db: Session = Depends(get_db),
    legacy: Optional[LegacyClaimsClient] = Depends(get_legacy_dep),
) -> ClaimOut:
    claim = _get_claim(db, claim_id)
    if claim.status not in ("needs_review", "writeback_failed"):
        raise HTTPException(409, "claim is {}".format(claim.status))
    return claim_out(pipeline.approve(db, claim, req.corrections, legacy))


@app.post("/claims/{claim_id}/reject", response_model=ClaimOut)
def reject_claim(claim_id: int, db: Session = Depends(get_db)) -> ClaimOut:
    claim = _get_claim(db, claim_id)
    if claim.status != "needs_review":
        raise HTTPException(409, "claim is {}".format(claim.status))
    claim.status = "rejected"
    db.commit()
    return claim_out(claim)
