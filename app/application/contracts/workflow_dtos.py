from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WorkflowAppointmentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    date: str
    time: str
    doctor: str
    status: str
