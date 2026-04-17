"""Generate the Mermaid diagram in docs/graph.md from the live compiled graph.

Usage:
    uv run python scripts/generate_graph_diagram.py

The script compiles the LangGraph graph with stub dependencies, calls
draw_mermaid(), and replaces the first ```mermaid ... ``` block in
docs/graph.md with the generated output.  Everything outside that block is
left untouched.
"""

import logging
import re
import sys
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from app.graph.builder import build_graph

DOCS_PATH = Path(__file__).parent.parent / "docs" / "graph.md"
MERMAID_BLOCK = re.compile(r"```mermaid\n.*?```", re.DOTALL)


class _Stub:
    def interpret(self, *a, **kw): ...
    def verify_identity(self, *a, **kw): ...
    def list_appointments(self, *a, **kw): return []
    def confirm_appointment(self, *a, **kw): ...
    def cancel_appointment(self, *a, **kw): ...


def main() -> None:
    graph = build_graph(
        logger=logging.getLogger("generate_graph_diagram"),
        provider=_Stub(),
        verification_service=_Stub(),
        appointment_service=_Stub(),
        max_verification_attempts=3,
        checkpointer=MemorySaver(),
    )

    mermaid = graph.get_graph().draw_mermaid()
    new_block = f"```mermaid\n{mermaid}```"

    original = DOCS_PATH.read_text()
    if not MERMAID_BLOCK.search(original):
        print(f"error: no mermaid block found in {DOCS_PATH}", file=sys.stderr)
        sys.exit(1)

    updated = MERMAID_BLOCK.sub(new_block, original, count=1)
    DOCS_PATH.write_text(updated)
    print(f"updated {DOCS_PATH}")


if __name__ == "__main__":
    main()
