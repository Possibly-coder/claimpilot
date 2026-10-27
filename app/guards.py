import re
from typing import List

from app.extract.heuristic import AMOUNT_RE, DATE_RES

DOLLARS_RE = re.compile(r"\b(\d[\d,]*(?:\.\d+)?) dollars\b", re.IGNORECASE)


def ambiguity_flags(text: str) -> List[str]:
    """Deterministic checks that force human review regardless of extractor confidence.

    A complete-looking extraction can still pick the deductible instead of the estimate,
    or the policy start date instead of the incident date.
    """
    flags: List[str] = []
    amounts = {m.replace(",", "") for m in AMOUNT_RE.findall(text) + DOLLARS_RE.findall(text)}
    if len(amounts) > 1:
        flags.append("email mentions {} different amounts; confirm the estimate".format(len(amounts)))
    dates = {m.group(0) for _, rx in DATE_RES for m in rx.finditer(text)}
    if len(dates) > 1:
        flags.append("email mentions {} different dates; confirm the incident date".format(len(dates)))
    return flags
