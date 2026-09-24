import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.persistence import database
from app.service import MarketService

ROOT = Path(__file__).resolve().parents[1]


class PrivateURL(str):
    def __repr__(self):
        return "'<redacted PostgreSQL test URL>'"


@pytest.fixture
def store():
    url = os.getenv("SALESBENCH_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Real PostgreSQL is required: set SALESBENCH_TEST_DATABASE_URL or run scripts/platform.ps1 test")
    schema = "sb_test_" + uuid4().hex
    assert re.fullmatch(r"sb_test_[0-9a-f]{32}", schema)
    owner = create_engine(url, hide_parameters=True)
    with owner.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    parsed = make_url(url)
    options = parsed.query.get("options", "") + f" -csearch_path={schema}"
    scoped_url = parsed.update_query_dict({"options": options.strip()}).render_as_string(hide_password=False)
    engine, sessions = database(scoped_url)
    cfg = Config(str(ROOT / "alembic.ini"))
    try:
        with engine.begin() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
        yield {"engine": engine, "sessions": sessions, "service": MarketService(sessions), "url": PrivateURL(scoped_url), "schema": schema}
    finally:
        engine.dispose()
        # Only the unique schema this fixture just created; never an existing database/schema.
        assert re.fullmatch(r"sb_test_[0-9a-f]{32}", schema)
        with owner.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        owner.dispose()
