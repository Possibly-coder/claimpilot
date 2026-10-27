import time
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.legacy_client import LegacyClaimsClient, LegacyWriteError
from app.schemas import ExtractedClaim, LossType
from legacy_api.main import create_app

CLAIM = ExtractedClaim(
    policy_number="POL-123456", claimant_name="Priya Sharma", incident_date=date(2026, 4, 3),
    loss_type=LossType.property_water, estimated_amount=2400.0,
)


def _client(app, max_attempts=8):
    return LegacyClaimsClient(http=TestClient(app), max_attempts=max_attempts, sleep=lambda s: None)


def test_retries_flaky_server_without_duplicates():
    app = create_app(failure_rate=0.6, rate_limit_per_sec=1000, seed=1)
    client = _client(app, max_attempts=20)
    refs = [client.submit(i, CLAIM) for i in range(1, 31)]
    assert len(set(refs)) == 30
    # Lost-response failures saved the claim server-side; idempotency keys stop duplicates.
    assert TestClient(app).get("/api/v1/claims/count").json()["count"] == 30


def test_same_claim_id_returns_same_ref():
    client = _client(create_app(failure_rate=0.0, rate_limit_per_sec=1000))
    assert client.submit(7, CLAIM) == client.submit(7, CLAIM)


def test_gives_up_after_max_attempts():
    calls = []

    def always_down(request):
        calls.append(request.headers["X-Idempotency-Key"])
        return httpx.Response(503)

    http = httpx.Client(base_url="http://legacy", transport=httpx.MockTransport(always_down))
    client = LegacyClaimsClient(http=http, max_attempts=3, sleep=lambda s: None)
    with pytest.raises(LegacyWriteError, match="gave up after 3 attempts"):
        client.submit(1, CLAIM)
    assert calls == ["claimpilot-1"] * 3


def test_rate_limit_is_retried():
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        time.sleep(seconds)

    app = create_app(failure_rate=0.0, rate_limit_per_sec=2)
    client = LegacyClaimsClient(http=TestClient(app), max_attempts=5, sleep=sleep)
    for i in range(3):
        client.submit(i, CLAIM)
    assert 1.0 in sleeps  # honoured Retry-After


def test_missing_fields_rejected_without_retry():
    client = _client(create_app(failure_rate=0.0, rate_limit_per_sec=1000))
    with pytest.raises(LegacyWriteError, match="rejected claim \\(400\\)"):
        client.submit(1, ExtractedClaim(policy_number="POL-123456"))
