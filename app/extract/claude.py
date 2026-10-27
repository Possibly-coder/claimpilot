import time
from typing import Any, Optional

from app.extract.base import Extractor, completeness, safe_claim
from app.schemas import ExtractedClaim, ExtractionResult, LossType

TOOL_NAME = "record_claim"

TOOL = {
    "name": TOOL_NAME,
    "description": "Record the structured first-notice-of-loss fields extracted from an insurance claim email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "policy_number": {
                "type": ["string", "null"],
                "description": "Normalize to POL-XXXXXX (6 digits). Null if absent.",
            },
            "claimant_name": {"type": ["string", "null"], "description": "Full name of the person filing."},
            "incident_date": {
                "type": ["string", "null"],
                "description": "YYYY-MM-DD date the loss happened. Not the policy start date, not today's date.",
            },
            "loss_type": {
                "type": ["string", "null"],
                "enum": [t.value for t in LossType] + [None],
            },
            "estimated_amount": {
                "type": ["number", "null"],
                "description": "Claimant's estimated loss/repair cost. Not the deductible, not the premium.",
            },
            "description": {"type": ["string", "null"], "description": "One-sentence summary of what happened."},
            "confidence": {
                "type": "number",
                "description": "0 to 1: your confidence that every field above is correct.",
            },
            "ambiguities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Anything a human reviewer should double-check.",
            },
        },
        "required": [
            "policy_number", "claimant_name", "incident_date", "loss_type",
            "estimated_amount", "description", "confidence", "ambiguities",
        ],
    },
}

SYSTEM = """You extract first-notice-of-loss (FNOL) data from insurance claim emails and attached documents.
Always respond by calling the record_claim tool exactly once.
Rules:
- Use null for anything not stated. Never guess a policy number or amount.
- Emails may mention several dates (policy start, renewal, email date). incident_date is when the loss happened.
- Emails may mention several amounts (deductible, premium, estimate). estimated_amount is the claimant's estimate of the loss.
- Slash dates: if sender locale is IN or GB they are DD/MM/YYYY; if US they are MM/DD/YYYY.
- List real ambiguities so a human can check them."""


class ClaudeExtractor(Extractor):
    name = "claude"

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-haiku-5-5",
        price_in_per_mtok: float = 0.10,
        price_out_per_mtok: float = 0.50,
        client: Optional[Any] = None,
    ) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        self.client = client
        self.model = model
        self.price_in = price_in_per_mtok
        self.price_out = price_out_per_mtok
        self.name = "claude:" + model

    def extract(self, text: str, locale: Optional[str] = None) -> ExtractionResult:
        started = time.perf_counter()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM,
            tools=[TOOL],
            messages=[{
                "role": "user",
                "content": "Sender locale: {}\n\n<email>\n{}\n</email>".format(locale or "unknown", text),
            }],
        )
        latency_ms = (time.perf_counter() - started) * 1000

        data = None
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == TOOL_NAME:
                data = dict(block.input)
                break

        usage = getattr(response, "usage", None)
        cost = 0.0
        if usage is not None:
            cost = (usage.input_tokens * self.price_in + usage.output_tokens * self.price_out) / 1_000_000

        if data is None:
            return ExtractionResult(
                claim=ExtractedClaim(), confidence=0.0, extractor=self.name,
                latency_ms=latency_ms, cost_usd=cost, notes=["model did not call record_claim"],
            )

        claim, notes = safe_claim(data)
        notes.extend("model: " + a for a in data.get("ambiguities") or [])
        try:
            model_conf = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            model_conf = 0.0
        # Self-reported confidence alone is unreliable; cap it by how complete the extraction is.
        confidence = min(max(model_conf, 0.0), 1.0, completeness(claim))
        return ExtractionResult(
            claim=claim, confidence=confidence, extractor=self.name,
            latency_ms=latency_ms, cost_usd=cost, notes=notes,
        )
