import pytest
from app.db.connection import init_db


@pytest.fixture(autouse=True, scope="session")
def setup_db():
    """Ensure schema is created before any test runs."""
    init_db()
