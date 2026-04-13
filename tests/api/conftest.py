import pytest

from app.api import routes
from app.graph.builder import build_graph


@pytest.fixture(autouse=True)
def reset_api_graph():
    routes.graph = build_graph()
