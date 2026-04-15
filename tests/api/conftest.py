import pytest

from app.main import app, reset_runtime


@pytest.fixture(autouse=True)
def reset_api_graph():
    reset_runtime(app)
