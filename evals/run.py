"""Score an extractor against evals/data/cases.jsonl.

    python -m evals.run --extractor heuristic
    ANTHROPIC_API_KEY=... python -m evals.run --extractor claude
"""
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers tables)
from app.config import Settings
from app.db import Base
from app.documents import infer_locale
from app.extract import get_extractor
from app.guards import ambiguity_flags
from app.routing import route
from app.schemas import REQUIRED_FIELDS
from app.seed_data import seed_policies
from app.validate import validate_claim

CASES = Path(__file__).parent / "data" / "cases.jsonl"
RESULTS = Path(__file__).parent / "results"


def field_correct(field: str, expected: Any, got: Any) -> bool:
    if got is None:
        return False
    if field == "claimant_name":
        return " ".join(str(got).lower().split()) == " ".join(str(expected).lower().split())
    if field == "estimated_amount":
        return abs(float(got) - float(expected)) <= 0.01 * float(expected)
    if field == "loss_type":
        return getattr(got, "value", got) == expected
    if field == "incident_date":
        return str(got) == expected
    return str(got).upper() == str(expected).upper()


def run(extractor_name: str, limit: int) -> Dict[str, Any]:
    cfg = Settings()
    cfg.extractor = extractor_name
    extractor = get_extractor(cfg)
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    if limit:
        cases = cases[:limit]

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    seed_policies(db)

    correct = {f: 0 for f in REQUIRED_FIELDS}
    all_correct = 0
    latency = 0.0
    cost = 0.0
    errors = 0
    failures: List[Dict[str, Any]] = []
    # routing outcomes, with and without the deterministic ambiguity guard
    auto = {"guarded": 0, "unguarded": 0}
    unsafe = {"guarded": 0, "unguarded": 0}
    review_reasons: Counter = Counter()

    for case in cases:
        text = "Subject: {}\n\n{}".format(case["subject"], case["body"])
        try:
            result = extractor.extract(text, infer_locale(case["sender"]))
        except Exception as exc:
            errors += 1
            failures.append({"case": case["id"], "field": "*", "expected": "-", "got": "error: {}".format(exc)})
            continue
        latency += result.latency_ms
        cost += result.cost_usd
        ok_all = True
        for f in REQUIRED_FIELDS:
            got = getattr(result.claim, f)
            if field_correct(f, case["expected"][f], got):
                correct[f] += 1
            else:
                ok_all = False
                failures.append({"case": case["id"], "field": f, "expected": case["expected"][f],
                                 "got": getattr(got, "value", got)})
        all_correct += ok_all

        validation = validate_claim(db, result.claim)
        guard = ambiguity_flags(text)
        for mode, flags in (("guarded", guard), ("unguarded", [])):
            decision, reasons = route(result, validation, cfg.auto_approve_limit, cfg.min_confidence, flags)
            if decision == "auto":
                auto[mode] += 1
                unsafe[mode] += not ok_all
            elif mode == "guarded":
                review_reasons.update({_reason_kind(x, guard) for x in reasons})

    db.close()
    n = len(cases)
    return {
        "extractor": extractor.name,
        "n": n,
        "field_accuracy": {f: correct[f] / n for f in REQUIRED_FIELDS},
        "all_fields_correct": all_correct / n,
        "avg_latency_ms": latency / max(n - errors, 1),
        "total_cost_usd": cost,
        "cost_per_claim_usd": cost / max(n - errors, 1),
        "errors": errors,
        "auto": auto,
        "unsafe": unsafe,
        "review_reasons": review_reasons,
        "failures": failures,
    }


def _reason_kind(reason: str, guard: List[str]) -> str:
    if reason.startswith("model: "):
        return "model listed an ambiguity (shown to reviewer, not blocking)"
    if reason.startswith("low extraction confidence"):
        return "low confidence"
    if reason.startswith("amount above"):
        return "amount above auto-submit limit"
    if reason in guard:
        return "ambiguity guard"
    return "validation: " + reason.split(" (")[0]


def to_markdown(r: Dict[str, Any]) -> str:
    lines = [
        "# Eval: {} ({} cases, {})".format(r["extractor"], r["n"], datetime.now().strftime("%Y-%m-%d %H:%M")),
        "",
        "| Field | Accuracy |",
        "|---|---|",
    ]
    for f, acc in r["field_accuracy"].items():
        lines.append("| {} | {:.1%} |".format(f, acc))
    lines += [
        "| **all 5 fields correct** | **{:.1%}** |".format(r["all_fields_correct"]),
        "",
        "- Avg latency: {:.0f} ms".format(r["avg_latency_ms"]),
        "- Cost per claim: ${:.5f} (total ${:.4f})".format(r["cost_per_claim_usd"], r["total_cost_usd"]),
        "- Errors: {}".format(r["errors"]),
        "",
        "## Routing (what actually reaches the legacy system untouched)",
        "",
        "| Mode | Auto-submitted | Auto-submitted with a wrong field |",
        "|---|---|---|",
        "| With ambiguity guard | {} / {} | **{}** |".format(r["auto"]["guarded"], r["n"], r["unsafe"]["guarded"]),
        "| Without guard | {} / {} | {} |".format(r["auto"]["unguarded"], r["n"], r["unsafe"]["unguarded"]),
        "",
        "## Why claims went to review (with guard; a claim can have several reasons)",
        "",
        "| Reason | Claims |",
        "|---|---|",
    ]
    for reason, count in r["review_reasons"].most_common():
        lines.append("| {} | {} |".format(reason, count))
    lines += [
        "",
        "## First 15 failures",
        "",
        "| Case | Field | Expected | Got |",
        "|---|---|---|---|",
    ]
    for fl in r["failures"][:15]:
        lines.append("| {case} | {field} | {expected} | {got} |".format(**fl))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", default="heuristic", choices=["heuristic", "claude"])
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    report = run(args.extractor, args.limit)
    md = to_markdown(report)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / "{}.md".format(args.extractor)
    out.write_text(md)
    print(md)
    print("saved to {}".format(out))


if __name__ == "__main__":
    main()
