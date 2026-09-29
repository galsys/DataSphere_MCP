from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import Environment, Identifier, SpaceRequest
from .objects import DatasphereObject, DatasphereObjectType


class ObjectWriteRequest(SpaceRequest):
    object_type: DatasphereObjectType
    technical_name: Identifier | None = None
    definition: dict[str, Any] = Field(min_length=1)
    confirmed: bool = False


class ObjectWriteResult(BaseModel):
    technical_name: str
    object_type: DatasphereObjectType
    definition: dict[str, Any]
    operation: str
