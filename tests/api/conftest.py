import pytest

from app.main import app
from app.api import routes


@pytest.fixture(autouse=True)
def reset_api_graph():
    routes.reset_runtime(app)
