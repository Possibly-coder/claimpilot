from datetime import date
from types import SimpleNamespace

from app.extract.claude import ClaudeExtractor
from app.extract.heuristic import HeuristicExtractor
from app.schemas import LossType

EMAIL = """Hello,
My name is Priya Sharma and I'm filing a claim on policy number POL 123456.
On 03/04/2026, a pipe burst under the kitchen sink and flooded the floor.
The repair estimate I received is $2,400.
Regards,
Priya Sharma"""


def test_heuristic_extracts_all_fields_us_locale():
    r = HeuristicExtractor().extract(EMAIL, "US")
    c = r.claim
    assert c.policy_number == "POL-123456"
    assert c.claimant_name == "Priya Sharma"
    assert c.incident_date == date(2026, 3, 4)
    assert c.loss_type == LossType.property_water
    assert c.estimated_amount == 2400.0
    assert r.confidence == 1.0


def test_heuristic_amount_without_thousands_separator():
    assert HeuristicExtractor().extract("Estimate is USD 1200.", "US").claim.estimated_amount == 1200.0


def test_heuristic_day_first_for_indian_sender():
    assert HeuristicExtractor().extract(EMAIL, "IN").claim.incident_date == date(2026, 4, 3)


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _fake_client(tool_input, input_tokens=1000, output_tokens=200):
    response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="record_claim", input=tool_input)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )
    return SimpleNamespace(messages=FakeMessages(response))


def test_claude_extractor_parses_tool_call_and_costs():
    client = _fake_client({
        "policy_number": "POL-123456", "claimant_name": "Priya Sharma", "incident_date": "2026-04-03",
        "loss_type": "property_water", "estimated_amount": 2400, "description": "Burst pipe.",
        "confidence": 0.95, "ambiguities": [],
    })
    ex = ClaudeExtractor(client=client, price_in_per_mtok=0.10, price_out_per_mtok=0.50)
    r = ex.extract(EMAIL, "IN")
    assert r.claim.incident_date == date(2026, 4, 3)
    assert r.confidence == 0.95
    assert abs(r.cost_usd - (1000 * 0.10 + 200 * 0.50) / 1_000_000) < 1e-12
    assert "Sender locale: IN" in client.messages.kwargs["messages"][0]["content"]


def test_claude_extractor_drops_invalid_field_and_caps_confidence():
    client = _fake_client({
        "policy_number": "POL-123456", "claimant_name": "Priya Sharma", "incident_date": "sometime in March",
        "loss_type": "property_water", "estimated_amount": 2400, "description": None,
        "confidence": 0.99, "ambiguities": ["date unclear"],
    })
    r = ClaudeExtractor(client=client).extract(EMAIL, "IN")
    assert r.claim.incident_date is None
    assert r.confidence == 0.8  # 4 of 5 required fields
    assert any("incident_date" in n for n in r.notes)
    assert "model: date unclear" in r.notes
