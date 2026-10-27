from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    holder_name: Mapped[str] = mapped_column(String(128))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    covered_types: Mapped[str] = mapped_column(String(256))  # comma-separated LossType values
    coverage_limit: Mapped[float] = mapped_column(Float)

    def covered(self) -> List[str]:
        return [t for t in self.covered_types.split(",") if t]


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    sender: Mapped[str] = mapped_column(String(256))
    subject: Mapped[str] = mapped_column(String(512), default="")
    raw_text: Mapped[str] = mapped_column(Text)
    extracted_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    extractor: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[float] = mapped_column(Float)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    # auto_submitted | needs_review | approved | rejected | writeback_failed
    status: Mapped[str] = mapped_column(String(32), index=True)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    legacy_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
