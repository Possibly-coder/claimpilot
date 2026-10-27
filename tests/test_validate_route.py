from datetime import date, timedelta

from app.routing import route
from app.schemas import ExtractedClaim, ExtractionResult, LossType
from app.validate import validate_claim


def _claim(policy, **overrides):
    data = dict(
        policy_number=policy["policy_number"],
        claimant_name=policy["holder_name"],
        incident_date=policy["start_date"] + timedelta(days=10),
        loss_type=LossType(policy["covered_types"].split(",")[0]),
        estimated_amount=1200.0,
    )
    data.update(overrides)
    return ExtractedClaim(**data)


def _result(claim, confidence=1.0):
    return ExtractionResult(claim=claim, confidence=confidence, extractor="test", latency_ms=1.0)


def test_valid_claim_routes_auto(db, policy):
    claim = _claim(policy)
    v = validate_claim(db, claim, today=date(2027, 12, 31))
    assert v.ok, v.issues
    assert route(_result(claim), v, auto_limit=5000, min_confidence=0.8) == ("auto", [])


def test_unknown_policy_and_outside_period(db, policy):
    v = validate_claim(db, _claim(policy, policy_number="POL-000000"), today=date(2027, 12, 31))
    assert "policy POL-000000 not found" in v.issues

    late = policy["end_date"] + timedelta(days=5)
    v = validate_claim(db, _claim(policy, incident_date=late), today=date(2027, 12, 31))
    assert "incident date outside policy period" in v.issues


def test_uncovered_loss_type(db, policy):
    covered = policy["covered_types"].split(",")
    uncovered = next(t for t in LossType if t.value not in covered)
    v = validate_claim(db, _claim(policy, loss_type=uncovered), today=date(2027, 12, 31))
    assert any("not covered" in i for i in v.issues)


def test_high_amount_and_low_confidence_go_to_review(db, policy):
    claim = _claim(policy, estimated_amount=8000.0)
    v = validate_claim(db, claim, today=date(2027, 12, 31))
    decision, reasons = route(_result(claim, confidence=0.6), v, auto_limit=5000, min_confidence=0.8)
    assert decision == "review"
    assert any("auto-submit limit" in r for r in reasons)
    assert any("low extraction confidence" in r for r in reasons)
