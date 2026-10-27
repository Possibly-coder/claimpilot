import os


def _normalize_db_url(url: str) -> str:
    # Render/Railway hand out postgres:// URLs; SQLAlchemy needs an explicit driver.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    def __init__(self) -> None:
        self.database_url = _normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///./claimpilot.db"))
        # auto = Claude if ANTHROPIC_API_KEY is set, else heuristic
        self.extractor = os.getenv("CLAIMPILOT_EXTRACTOR", "auto")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("CLAIMPILOT_MODEL", "claude-haiku-5-5")
        self.price_in_per_mtok = float(os.getenv("CLAIMPILOT_PRICE_IN_PER_MTOK", "0.10"))
        self.price_out_per_mtok = float(os.getenv("CLAIMPILOT_PRICE_OUT_PER_MTOK", "0.50"))
        # Empty = don't write back to the legacy system (claims stay in ClaimPilot).
        self.legacy_api_url = os.getenv("LEGACY_API_URL", "")
        self.auto_approve_limit = float(os.getenv("CLAIMPILOT_AUTO_LIMIT", "5000"))
        self.min_confidence = float(os.getenv("CLAIMPILOT_MIN_CONFIDENCE", "0.8"))


settings = Settings()
