from ..models.common import Environment, Identifier, Result
from ..models.tasks import TaskLog, TaskLogRequest, TaskStatus
from .common import READ_METADATA, invoke


def register(mcp, runtime):
    @mcp.tool(**READ_METADATA)
    async def get_task_status(environment: Environment, space: Identifier,
                              log_id: Identifier) -> Result[TaskStatus]:
        """Read the status of a task run by its SAP task log ID."""
        return await invoke(runtime, "get_task_status", {
            "environment": environment, "space": space, "log_id": log_id,
        }, lambda: runtime.services(environment).tasks.get_task_status(
            TaskLogRequest(environment=environment, space=space, log_id=log_id)), Result[TaskStatus])

    @mcp.tool(**READ_METADATA)
    async def get_task_log(environment: Environment, space: Identifier,
                           log_id: Identifier) -> Result[TaskLog]:
        """Read detailed information for a task run by its SAP task log ID."""
        return await invoke(runtime, "get_task_log", {
            "environment": environment, "space": space, "log_id": log_id,
        }, lambda: runtime.services(environment).tasks.get_task_log(
            TaskLogRequest(environment=environment, space=space, log_id=log_id)), Result[TaskLog])
