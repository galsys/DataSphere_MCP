from ..models.common import Environment, Identifier, Result
from ..models.objects import DatasphereObjectType
from ..models.writes import ObjectWriteRequest, ObjectWriteResult
from .common import WRITE_METADATA, invoke


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
            definition=definition, confirmed=confirmed)), Result[ObjectWriteResult])

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
            Result[ObjectWriteResult])
