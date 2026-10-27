# Eval: heuristic (80 cases, 2026-10-28 02:13)

| Field | Accuracy |
|---|---|
| policy_number | 100.0% |
| claimant_name | 100.0% |
| incident_date | 58.8% |
| loss_type | 45.0% |
| estimated_amount | 37.5% |
| **all 5 fields correct** | **6.2%** |

- Avg latency: 0 ms
- Cost per claim: $0.00000 (total $0.0000)
- Errors: 0

## Routing (what actually reaches the legacy system untouched)

| Mode | Auto-submitted | Auto-submitted with a wrong field |
|---|---|---|
| With ambiguity guard | 2 / 80 | **0** |
| Without guard | 25 / 80 | 23 |

## Why claims went to review (with guard; a claim can have several reasons)

| Reason | Claims |
|---|---|
| ambiguity guard | 53 |
| validation: missing loss_type | 44 |
| validation: missing estimated_amount | 17 |
| low confidence | 10 |
| amount above auto-submit limit | 10 |
| validation: amount exceeds coverage limit | 1 |

## First 15 failures

| Case | Field | Expected | Got |
|---|---|---|---|
| case-001 | estimated_amount | 1200.0 | 500.0 |
| case-003 | loss_type | property_water | None |
| case-004 | incident_date | 2026-06-18 | 2026-02-19 |
| case-004 | loss_type | auto_theft | None |
| case-004 | estimated_amount | 18000.0 | 500.0 |
| case-005 | incident_date | 2026-05-30 | 2026-01-03 |
| case-005 | loss_type | property_water | None |
| case-005 | estimated_amount | 1200.0 | None |
| case-006 | incident_date | 2026-08-31 | 2026-03-07 |
| case-006 | loss_type | property_water | None |
| case-006 | estimated_amount | 18000.0 | 500.0 |
| case-007 | loss_type | property_water | None |
| case-007 | estimated_amount | 7200.0 | None |
| case-008 | loss_type | property_water | None |
| case-008 | estimated_amount | 1200.0 | 500.0 |
