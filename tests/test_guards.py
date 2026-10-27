from app.guards import ambiguity_flags


def test_single_amount_and_date_not_flagged():
    assert ambiguity_flags("On 2026-03-04 a pipe burst. Estimate is $2,400.") == []


def test_deductible_before_estimate_is_flagged():
    flags = ambiguity_flags("My deductible is $500. The repair estimate is about 1,200 dollars.")
    assert flags == ["email mentions 2 different amounts; confirm the estimate"]


def test_policy_start_and_incident_dates_flagged():
    flags = ambiguity_flags("I've had this policy since 11 January 2026. On 24 July 2026 my car was stolen.")
    assert flags == ["email mentions 2 different dates; confirm the incident date"]


def test_same_amount_repeated_is_not_ambiguous():
    assert ambiguity_flags("Estimate $1,200. Again, the total is $1200.") == []
