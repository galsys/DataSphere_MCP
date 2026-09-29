from typing import Any

from pydantic import BaseModel, Field

from .common import Identifier, SpaceRequest


class TaskLogRequest(SpaceRequest):
    log_id: Identifier


class TaskStatus(BaseModel):
    log_id: str
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskLog(BaseModel):
    log_id: str
    details: dict[str, Any]
