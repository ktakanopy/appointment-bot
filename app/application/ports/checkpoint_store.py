from __future__ import annotations

from typing import Protocol


class CheckpointStore(Protocol):
    def build_checkpointer(self) -> object:
        ...
