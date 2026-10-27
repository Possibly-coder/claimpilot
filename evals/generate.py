"""Generate a deterministic eval set of realistic FNOL emails with ground truth.

    python -m evals.generate --n 80
"""
import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from app.seed_data import policy_rows

OUT = Path(__file__).parent / "data" / "cases.jsonl"
LAST_INCIDENT = date(2026, 10, 20)

DOMAINS = [("example.com", "US", 0.5), ("example.co.in", "IN", 0.3), ("example.co.uk", "GB", 0.2)]

# (phrase, is_obvious) -- non-obvious phrasings have no giveaway keyword.
LOSS_PHRASES = {
    "auto_collision": [
        ("I was rear-ended at a traffic light and the bumper is crushed.", True),
        ("There was a collision at the intersection near my office.", True),
        ("Someone backed into my parked car in the mall lot and drove off.", False),
    ],
    "auto_theft": [
        ("My car was stolen from outside my building.", True),
        ("My car was taken from the driveway overnight; the police report is attached.", False),
    ],
    "property_water": [
        ("A pipe burst under the kitchen sink and flooded the floor.", True),
        ("The upstairs bathroom overflowed and soaked through our living room ceiling.", False),
    ],
    "property_fire": [
        ("A small fire started in the kitchen and damaged the cabinets.", True),
        ("A grease flare-up on the stove scorched the cabinets and the wall.", False),
    ],
}


def fmt_date(d: date, style: str, locale: str) -> str:
    if style == "iso":
        return d.isoformat()
    if style == "slash":
        return d.strftime("%d/%m/%Y") if locale in ("IN", "GB") else d.strftime("%m/%d/%Y")
    if style == "dmy_text":
        return "{} {}".format(d.day, d.strftime("%B %Y"))
    return "{} {}, {}".format(d.strftime("%B"), d.day, d.year)


def fmt_policy(num: str, rng: random.Random) -> str:
    digits = num.split("-")[1]
    return rng.choice([
        "POL-" + digits,
        "policy number POL " + digits,
        "Policy #: POL" + digits,
        "pol-" + digits,
    ])


def fmt_amount(amount: float, rng: random.Random) -> str:
    return rng.choice([
        "${:,.0f}".format(amount),
        "USD {:.0f}".format(amount),
        "${:,.2f}".format(amount),
        "about {:,.0f} dollars".format(amount),
    ])


def make_case(i: int, policy: dict, rng: random.Random) -> dict:
    domain, locale = rng.choices([(d, l) for d, l, _ in DOMAINS], weights=[w for _, _, w in DOMAINS])[0]
    first, last = policy["holder_name"].split(" ", 1)
    sender = "{}.{}@{}".format(first.lower(), last.lower(), domain)

    loss_type = rng.choice(policy["covered_types"].split(","))
    phrase, _ = rng.choice(LOSS_PHRASES[loss_type])

    end = min(policy["end_date"], LAST_INCIDENT)
    span = max((end - policy["start_date"]).days, 1)
    incident = policy["start_date"] + timedelta(days=rng.randint(0, span))
    date_style = rng.choice(["iso", "slash", "slash", "dmy_text", "mdy_text"])
    amount = float(rng.choice([450, 1200, 2400, 3850, 4999, 7200, 12500, 18000]))

    lines = ["Hello,"]
    intro = rng.choice(["name", "label", "signature_only"])
    if intro == "name":
        lines.append("My name is {} and I'm filing a claim on {}.".format(policy["holder_name"], fmt_policy(policy["policy_number"], rng)))
    elif intro == "label":
        lines.append("Name: {}\nPolicy: {}".format(policy["holder_name"], fmt_policy(policy["policy_number"], rng)))
    else:
        lines.append("I need to file a claim on {}.".format(fmt_policy(policy["policy_number"], rng)))

    if rng.random() < 0.3:
        lines.append("I've had this policy since {}.".format(fmt_date(policy["start_date"], date_style, locale)))
    sentence = phrase if phrase.startswith("I ") else phrase[0].lower() + phrase[1:]
    lines.append("On {}, {}".format(fmt_date(incident, date_style, locale), sentence))
    if rng.random() < 0.3:
        lines.append("I understand my deductible is $500.")
    lines.append("The repair estimate I received is {}.".format(fmt_amount(amount, rng)))
    lines.append("Please let me know what you need from me.")
    lines.append("{},\n{}".format(rng.choice(["Regards", "Thanks", "Sincerely"]), policy["holder_name"]))

    return {
        "id": "case-{:03d}".format(i),
        "sender": sender,
        "subject": rng.choice(["New claim", "Claim notification", "Need help with a claim", "FNOL"]),
        "body": "\n".join(lines),
        "expected": {
            "policy_number": policy["policy_number"],
            "claimant_name": policy["holder_name"],
            "incident_date": incident.isoformat(),
            "loss_type": loss_type,
            "estimated_amount": amount,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    policies = policy_rows()
    cases = [make_case(i + 1, rng.choice(policies), rng) for i in range(args.n)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for case in cases:
            f.write(json.dumps(case) + "\n")
    print("wrote {} cases to {}".format(len(cases), OUT))


if __name__ == "__main__":
    main()
