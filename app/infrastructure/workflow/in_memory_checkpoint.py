from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver


class InMemoryCheckpointStore:
    def build_checkpointer(self):
        return InMemorySaver()
