from __future__ import annotations

from typing import Any, Protocol


class CheckpointStore(Protocol):
    def build_checkpointer(self) -> Any:
        ...
