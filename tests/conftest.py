import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CLAIMPILOT_EXTRACTOR"] = "heuristic"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("LEGACY_API_URL", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.seed_data import policy_rows, seed_policies  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    seed_policies(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def policy():
    return policy_rows()[0]


@pytest.fixture()
def client(db):
    from app import main

    main._legacy = None
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
