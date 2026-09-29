from ..adapters.base import TaskAdapter
from ..models.common import Result
from ..models.tasks import TaskLog, TaskLogRequest, TaskStatus
from ..security import authorize


class TaskService:
    def __init__(self, adapter: TaskAdapter):
        self.adapter = adapter

    async def get_task_status(self, request: TaskLogRequest) -> Result[TaskStatus]:
        request = TaskLogRequest.model_validate(request.model_dump())
        authorize(request.environment)
        payload = await self.adapter.get_task_log(request, "status")
        if not isinstance(payload, dict):
            raise ValueError("invalid task status")
        return Result[TaskStatus](environment=request.environment, space=request.space,
            data=TaskStatus(log_id=request.log_id, status=payload.get("status"), metadata=payload))

    async def get_task_log(self, request: TaskLogRequest) -> Result[TaskLog]:
        request = TaskLogRequest.model_validate(request.model_dump())
        authorize(request.environment)
        payload = await self.adapter.get_task_log(request, "details")
        if not isinstance(payload, dict):
            raise ValueError("invalid task log")
        return Result[TaskLog](environment=request.environment, space=request.space,
            data=TaskLog(log_id=request.log_id, details=payload))
