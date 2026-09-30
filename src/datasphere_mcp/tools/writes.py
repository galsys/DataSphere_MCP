from ..models.common import Environment, Identifier, Result, Risk
from ..models.objects import DatasphereObjectType
from ..models.writes import (
    ObjectDeleteRequest, ObjectDeleteResult, ObjectWriteRequest, ObjectWriteResult,
)
from .common import DESTRUCTIVE_METADATA, WRITE_METADATA, invoke


def register(mcp, runtime):
    @mcp.tool(**WRITE_METADATA)
    async def create_object(environment: Environment, space: Identifier,
                            object_type: DatasphereObjectType, definition: dict,
                            confirmed: bool = False) -> Result[ObjectWriteResult]:
        """Create a Datasphere object from an inline JSON definition."""
        return await invoke(runtime, "create_object", {
            "environment": environment, "space": space, "object_type": object_type,
        }, lambda: runtime.services(environment).writes.create_object(ObjectWriteRequest(
            environment=environment, space=space, object_type=object_type,
            definition=definition, confirmed=confirmed)), Result[ObjectWriteResult], Risk.WRITE)

    @mcp.tool(**WRITE_METADATA)
    async def update_object(environment: Environment, space: Identifier,
                            object_type: DatasphereObjectType, technical_name: Identifier,
                            definition: dict, confirmed: bool = False) -> Result[ObjectWriteResult]:
        """Update a Datasphere object from an inline JSON definition."""
        return await invoke(runtime, "update_object", {
            "environment": environment, "space": space, "object_type": object_type,
            "technical_name": technical_name,
        }, lambda: runtime.services(environment).writes.update_object(ObjectWriteRequest(
            environment=environment, space=space, object_type=object_type,
            technical_name=technical_name, definition=definition, confirmed=confirmed)),
            Result[ObjectWriteResult], Risk.WRITE)

    @mcp.tool(**DESTRUCTIVE_METADATA)
    async def delete_object(environment: Environment, space: Identifier,
                            object_type: DatasphereObjectType, technical_name: Identifier,
                            delete_object: bool = False) -> Result[ObjectDeleteResult]:
        """Delete a DEV Datasphere object after server opt-in and explicit confirmation."""
        return await invoke(runtime, "delete_object", {
            "environment": environment, "space": space, "object_type": object_type,
            "technical_name": technical_name,
        }, lambda: runtime.services(environment).writes.delete_object(ObjectDeleteRequest(
            environment=environment, space=space, object_type=object_type,
            technical_name=technical_name, confirmed=confirmed)),
            Result[ObjectDeleteResult], Risk.DESTRUCTIVE)
