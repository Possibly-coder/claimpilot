"""Mock of a carrier's legacy claims system.

Deliberately unpleasant, like the real ones: XML only, rate-limited, and it fails
randomly -- sometimes *after* saving the claim, so clients that retry without an
idempotency key create duplicates.
"""
import os
import random
import threading
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from fastapi import FastAPI, Header, Request, Response

REQUIRED = ["PolicyNumber", "ClaimantName", "LossDate", "LossType", "EstimatedAmount"]


def _xml(status_code: int, root: str, **children: str) -> Response:
    el = ET.Element(root)
    for tag, value in children.items():
        ET.SubElement(el, tag).text = value
    return Response(ET.tostring(el, encoding="utf-8"), status_code=status_code, media_type="application/xml")


def create_app(
    failure_rate: float = 0.2,
    rate_limit_per_sec: int = 5,
    seed: Optional[int] = None,
) -> FastAPI:
    app = FastAPI(title="Legacy Claims System (mock)")
    rng = random.Random(seed)
    lock = threading.Lock()
    refs: Dict[str, str] = {}
    claims: Dict[str, Dict[str, str]] = {}
    recent: List[float] = []

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "claims_stored": len(claims)}

    @app.get("/api/v1/claims/count")
    def count() -> dict:
        return {"count": len(claims)}

    @app.post("/api/v1/claims")
    async def create_claim(request: Request, x_idempotency_key: Optional[str] = Header(None)) -> Response:
        with lock:
            now = time.monotonic()
            recent[:] = [t for t in recent if now - t < 1.0]
            if len(recent) >= rate_limit_per_sec:
                resp = _xml(429, "Error", Message="Too many requests")
                resp.headers["Retry-After"] = "1"
                return resp
            recent.append(now)

        try:
            root = ET.fromstring(await request.body())
        except ET.ParseError:
            return _xml(400, "Error", Message="Malformed XML")
        fields = {child.tag: (child.text or "") for child in root}
        missing = [f for f in REQUIRED if not fields.get(f)]
        if missing:
            return _xml(400, "Error", Message="Missing: " + ",".join(missing))

        with lock:
            if x_idempotency_key and x_idempotency_key in refs:
                return _xml(200, "Result", ClaimRef=refs[x_idempotency_key])

            roll = rng.random()
            if roll < failure_rate / 2:
                return _xml(500, "Error", Message="Internal error")

            ref = "LC-{:06d}".format(len(claims) + 1)
            claims[ref] = fields
            if x_idempotency_key:
                refs[x_idempotency_key] = ref

            if roll < failure_rate:
                # Saved, but the client never hears about it.
                return _xml(500, "Error", Message="Gateway timeout")
        return _xml(200, "Result", ClaimRef=ref)

    return app


app = create_app(
    failure_rate=float(os.getenv("LEGACY_FAILURE_RATE", "0.2")),
    rate_limit_per_sec=int(os.getenv("LEGACY_RATE_LIMIT_PER_SEC", "5")),
)
