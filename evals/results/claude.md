# Eval: claude:claude-haiku-5-5 (80 cases, 2026-10-28 02:12)

| Field | Accuracy |
|---|---|
| policy_number | 100.0% |
| claimant_name | 100.0% |
| incident_date | 100.0% |
| loss_type | 100.0% |
| estimated_amount | 100.0% |
| **all 5 fields correct** | **100.0%** |

- Avg latency: 3192 ms
- Cost per claim: $0.00039 (total $0.0314)
- Errors: 0

## Routing (what actually reaches the legacy system untouched)

| Mode | Auto-submitted | Auto-submitted with a wrong field |
|---|---|---|
| With ambiguity guard | 0 / 80 | **0** |
| Without guard | 0 / 80 | 0 |
| Guard on, model's ambiguity notes shown to reviewer but not blocking | 14 / 80 | 0 |

## Why claims went to review (with guard; a claim can have several reasons)

| Reason | Claims |
|---|---|
| model listed an ambiguity | 80 |
| ambiguity guard | 53 |
| amount above auto-submit limit | 27 |
| low confidence | 9 |
| validation: amount exceeds coverage limit | 5 |

## First 15 failures

| Case | Field | Expected | Got |
|---|---|---|---|
