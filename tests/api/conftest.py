import pytest

from app.api import routes


@pytest.fixture(autouse=True)
def reset_api_graph():
    routes.reset_runtime()
