import io
from datetime import timedelta

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app import main
from app.legacy_client import LegacyClaimsClient
from legacy_api.main import create_app


def _email(policy, policy_number=None, amount="$1,200"):
    incident = policy["start_date"] + timedelta(days=10)
    loss = policy["covered_types"].split(",")[0]
    phrase = {
        "auto_collision": "I was rear-ended at a light.",
        "auto_theft": "my car was stolen.",
        "property_water": "a pipe burst in the kitchen.",
        "property_fire": "a small fire damaged the kitchen.",
    }[loss]
    return (
        "My name is {name}, policy {num}.\nOn {date}, {phrase}\nThe repair estimate is {amount}.\nRegards,\n{name}"
    ).format(name=policy["holder_name"], num=policy_number or policy["policy_number"],
             date=incident.isoformat(), phrase=phrase, amount=amount)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "extractor": "heuristic", "legacy_writeback": False}


def test_clean_claim_is_auto_submitted(client, policy):
    r = client.post("/claims/intake", json={"sender": "a@example.com", "subject": "claim", "body": _email(policy)})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "auto_submitted", body["reasons"]
    assert body["extracted"]["policy_number"] == policy["policy_number"]


def test_bad_policy_goes_to_review_then_human_fixes_it(client, policy):
    r = client.post("/claims/intake", json={
        "sender": "a@example.com", "body": _email(policy, policy_number="POL-000001")})
    body = r.json()
    assert body["status"] == "needs_review"
    assert "policy POL-000001 not found" in body["reasons"]

    queue = client.get("/claims", params={"status": "needs_review"}).json()
    assert [c["id"] for c in queue] == [body["id"]]

    r = client.post("/claims/{}/approve".format(body["id"]),
                    json={"corrections": {"policy_number": policy["policy_number"]}})
    assert r.json()["status"] == "approved"
    assert r.json()["extracted"]["policy_number"] == policy["policy_number"]
    assert client.post("/claims/{}/reject".format(body["id"])).status_code == 409


def test_deductible_mention_forces_review_even_when_complete(client, policy):
    body = _email(policy).replace("The repair estimate", "My deductible is $500. The repair estimate")
    r = client.post("/claims/intake", json={"sender": "a@example.com", "body": body}).json()
    assert r["status"] == "needs_review"
    assert r["extracted"]["estimated_amount"] == 500.0  # the baseline extractor really does grab the deductible
    assert any("different amounts" in reason for reason in r["reasons"])


def test_pdf_attachment(client, policy):
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf)
    y = 800
    for line in _email(policy).splitlines():
        pdf.drawString(50, y, line)
        y -= 20
    pdf.save()
    r = client.post(
        "/claims/intake/upload",
        data={"sender": "a@example.com", "subject": "FNOL form"},
        files={"file": ("fnol.pdf", buf.getvalue(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["extracted"]["policy_number"] == policy["policy_number"]
    assert "[Attachment: fnol.pdf]" in r.json()["raw_text"]


def test_unsupported_attachment(client):
    r = client.post("/claims/intake/upload", data={"sender": "a@example.com"},
                    files={"file": ("photo.jpg", b"\xff\xd8", "image/jpeg")})
    assert r.status_code == 415


def test_writeback_to_flaky_legacy_system(client, policy):
    legacy_app = create_app(failure_rate=0.5, rate_limit_per_sec=1000, seed=11)
    legacy = LegacyClaimsClient(http=TestClient(legacy_app), max_attempts=20, sleep=lambda s: None)
    main.app.dependency_overrides[main.get_legacy_dep] = lambda: legacy

    for _ in range(5):
        r = client.post("/claims/intake", json={"sender": "a@example.com", "body": _email(policy)})
        assert r.json()["status"] == "auto_submitted", r.json()["reasons"]
        assert r.json()["legacy_ref"].startswith("LC-")
    assert TestClient(legacy_app).get("/api/v1/claims/count").json()["count"] == 5
