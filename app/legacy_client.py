import time
import xml.etree.ElementTree as ET
from typing import Callable, Optional

import httpx

from app.schemas import ExtractedClaim


class LegacyWriteError(Exception):
    pass


def claim_to_xml(claim: ExtractedClaim) -> bytes:
    root = ET.Element("Claim")
    values = {
        "PolicyNumber": claim.policy_number,
        "ClaimantName": claim.claimant_name,
        "LossDate": claim.incident_date.isoformat() if claim.incident_date else None,
        "LossType": claim.loss_type.value if claim.loss_type else None,
        "EstimatedAmount": "{:.2f}".format(claim.estimated_amount) if claim.estimated_amount is not None else None,
        "Description": claim.description,
    }
    for tag, value in values.items():
        ET.SubElement(root, tag).text = value or ""
    return ET.tostring(root, encoding="utf-8")


class LegacyClaimsClient:
    """Client for the carrier's legacy claims API: XML, rate-limited, and flaky."""

    def __init__(
        self,
        base_url: str = "",
        http: Optional[httpx.Client] = None,
        max_attempts: int = 5,
        base_delay: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http or httpx.Client(base_url=base_url, timeout=10.0)
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.sleep = sleep

    def submit(self, claim_id: int, claim: ExtractedClaim) -> str:
        # Same key on every retry: if the server committed but the response was lost,
        # the retry returns the original reference instead of creating a duplicate claim.
        headers = {
            "Content-Type": "application/xml",
            "X-Idempotency-Key": "claimpilot-{}".format(claim_id),
        }
        body = claim_to_xml(claim)
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self.http.post("/api/v1/claims", content=body, headers=headers)
            except httpx.TransportError as exc:
                last_error = "transport error: {}".format(exc)
                self.sleep(self.base_delay * 2 ** (attempt - 1))
                continue

            if resp.status_code == 200:
                ref = ET.fromstring(resp.content).findtext("ClaimRef")
                if not ref:
                    raise LegacyWriteError("legacy API returned 200 without ClaimRef")
                return ref
            if resp.status_code == 429:
                last_error = "rate limited"
                self.sleep(float(resp.headers.get("Retry-After", self.base_delay * 2 ** (attempt - 1))))
                continue
            if resp.status_code >= 500:
                last_error = "server error {}".format(resp.status_code)
                self.sleep(self.base_delay * 2 ** (attempt - 1))
                continue
            raise LegacyWriteError("legacy API rejected claim ({}): {}".format(resp.status_code, resp.text[:200]))

        raise LegacyWriteError("gave up after {} attempts: {}".format(self.max_attempts, last_error))
