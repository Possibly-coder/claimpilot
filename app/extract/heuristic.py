import re
import time
from datetime import date
from typing import List, Optional, Tuple

from app.extract.base import Extractor, completeness
from app.schemas import ExtractedClaim, ExtractionResult, LossType

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june",
         "july", "august", "september", "october", "november", "december"]
    )
}
_MONTH_ALT = "|".join(m.capitalize() for m in MONTHS)

POLICY_RE = re.compile(r"\bPOL[\s\-#:]*(\d{6})\b", re.IGNORECASE)
NAME_RES = [
    re.compile(r"\b[Mm]y name is ([A-Z][a-z]+(?: [A-Z][a-z]+)+)"),
    re.compile(r"\b(?:Name|Claimant|Insured)\s*:\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)"),
    re.compile(r"(?:Regards|Thanks|Thank you|Sincerely|Best),?\s*\n\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)"),
]
DATE_RES = [
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),
    ("slash", re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")),
    ("dmy_text", re.compile(r"\b(\d{1,2}) (" + _MONTH_ALT + r") (\d{4})\b")),
    ("mdy_text", re.compile(r"\b(" + _MONTH_ALT + r") (\d{1,2}),? (\d{4})\b")),
]
AMOUNT_RE = re.compile(r"(?:\$|USD ?)(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")
LOSS_KEYWORDS = [
    (LossType.auto_theft, ["stolen", "theft", "broke into my car", "carjack"]),
    (LossType.property_fire, ["fire", "smoke", "burned", "flames"]),
    (LossType.property_water, ["water", "leak", "flood", "pipe burst", "burst pipe"]),
    (LossType.auto_collision, ["collision", "crash", "rear-ended", "rear ended", "hit my car", "accident"]),
]


def _parse_date(text: str, locale: Optional[str]) -> Optional[date]:
    """Naive baseline: returns the first date-looking thing in the text."""
    day_first = locale in ("IN", "GB")
    hits: List[Tuple[int, date]] = []
    for kind, rx in DATE_RES:
        for m in rx.finditer(text):
            try:
                if kind == "iso":
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif kind == "slash":
                    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    d = date(y, b, a) if day_first else date(y, a, b)
                elif kind == "dmy_text":
                    d = date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
                else:
                    d = date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
            except ValueError:
                continue
            hits.append((m.start(), d))
    if not hits:
        return None
    return min(hits)[1]


class HeuristicExtractor(Extractor):
    name = "heuristic"

    def extract(self, text: str, locale: Optional[str] = None) -> ExtractionResult:
        started = time.perf_counter()
        claim = ExtractedClaim()

        m = POLICY_RE.search(text)
        if m:
            claim.policy_number = "POL-" + m.group(1)

        for rx in NAME_RES:
            m = rx.search(text)
            if m:
                claim.claimant_name = m.group(1)
                break

        claim.incident_date = _parse_date(text, locale)

        lowered = text.lower()
        for loss_type, words in LOSS_KEYWORDS:
            if any(w in lowered for w in words):
                claim.loss_type = loss_type
                break

        m = AMOUNT_RE.search(text)
        if m:
            claim.estimated_amount = float(m.group(1).replace(",", ""))

        return ExtractionResult(
            claim=claim,
            confidence=completeness(claim),
            extractor=self.name,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
