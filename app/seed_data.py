import random
from datetime import date, timedelta
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Policy

FIRST = ["Aarav", "Priya", "James", "Maria", "Rohan", "Emily", "Wei", "Fatima", "Carlos", "Sneha",
         "David", "Aisha", "Michael", "Ananya", "Lucas", "Grace", "Vikram", "Olivia", "Arjun", "Sofia"]
LAST = ["Sharma", "Patel", "Smith", "Garcia", "Mehta", "Johnson", "Chen", "Khan", "Lopez", "Iyer",
        "Brown", "Rahman", "Davis", "Nair", "Silva", "Wilson", "Rao", "Taylor", "Kapoor", "Rossi"]
AUTO = ["auto_collision", "auto_theft"]
HOME = ["property_water", "property_fire"]


def policy_rows(n: int = 40, seed: int = 42) -> List[Dict]:
    """Deterministic policy book shared by the app seed and the eval generator."""
    rng = random.Random(seed)
    rows: List[Dict] = []
    used = set()
    while len(rows) < n:
        num = rng.randint(100000, 999999)
        if num in used:
            continue
        used.add(num)
        kind = rng.choice(["auto", "home", "both"])
        covered = AUTO if kind == "auto" else HOME if kind == "home" else AUTO + HOME
        start = date(2025, 6, 1) + timedelta(days=rng.randint(0, 365))
        rows.append({
            "policy_number": "POL-{}".format(num),
            "holder_name": "{} {}".format(rng.choice(FIRST), rng.choice(LAST)),
            "start_date": start,
            "end_date": start + timedelta(days=365),
            "covered_types": ",".join(covered),
            "coverage_limit": float(rng.choice([10000, 25000, 50000])),
        })
    return rows


def seed_policies(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Policy)):
        return
    db.add_all(Policy(**row) for row in policy_rows())
    db.commit()
