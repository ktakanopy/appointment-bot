from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"


def _imports_for(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_application_contracts_do_not_import_domain_models():
    contract_files = (APP_DIR / "application" / "contracts").rglob("*.py")

    for path in contract_files:
        imports = _imports_for(path)
        assert "app.domain.models" not in imports


def test_presenters_do_not_import_llm_provider_modules():
    presenter_files = (APP_DIR / "application" / "presenters").rglob("*.py")

    for path in presenter_files:
        imports = _imports_for(path)
        assert not any(module.startswith("app.llm") for module in imports)
        assert not any(module.startswith("app.infrastructure.llm") for module in imports)


def test_api_routes_do_not_import_domain_graph_or_infrastructure_logic():
    imports = _imports_for(APP_DIR / "api" / "routes.py")

    assert not any(module.startswith("app.domain") for module in imports)
    assert not any(module.startswith("app.graph") for module in imports)
    assert not any(module.startswith("app.infrastructure") for module in imports)


def test_graph_state_stays_behind_workflow_adapter_outside_graph_package():
    importers: set[str] = set()

    for path in APP_DIR.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("app/graph/"):
            continue
        imports = _imports_for(path)
        if "app.graph.state" in imports:
            importers.add(relative)

    assert importers == {"app/infrastructure/workflow/langgraph_runner.py"}
