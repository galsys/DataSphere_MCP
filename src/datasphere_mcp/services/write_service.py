from ..adapters.base import WriteAdapter
from ..exceptions import ResponseFormatError
from ..models.common import Result
from ..models.writes import (
    ObjectDeleteRequest, ObjectDeleteResult, ObjectWriteRequest, ObjectWriteResult,
)
from ..security import authorize_delete, authorize_write


class WriteService:
    def __init__(self, adapter: WriteAdapter, settings):
        self.adapter = adapter
        self.settings = settings

    async def create_object(self, request: ObjectWriteRequest) -> Result[ObjectWriteResult]:
        return await self._write(request, "create")

    async def update_object(self, request: ObjectWriteRequest) -> Result[ObjectWriteResult]:
        if not request.technical_name:
            raise ResponseFormatError()
        return await self._write(request, "update")

    async def delete_object(self, request: ObjectDeleteRequest) -> Result[ObjectDeleteResult]:
        request = ObjectDeleteRequest.model_validate(request.model_dump())
        authorize_delete(self.settings, request.environment, request.confirmed)
        await self.adapter.delete_object(request)
        return Result[ObjectDeleteResult](environment=request.environment, space=request.space,
            data=ObjectDeleteResult(technical_name=request.technical_name,
                                    object_type=request.object_type, deleted=True))

    async def _write(self, request: ObjectWriteRequest, operation: str) -> Result[ObjectWriteResult]:
        request = ObjectWriteRequest.model_validate(request.model_dump())
        authorize_write(self.settings, request.environment, request.confirmed)
        payload = await getattr(self.adapter, f"{operation}_object")(request)
        if not isinstance(payload, dict) or not payload:
            raise ResponseFormatError()
        name = request.technical_name or payload.get("technicalName") or payload.get("technical_name")
        if not isinstance(name, str):
            raise ResponseFormatError()
        return Result[ObjectWriteResult](environment=request.environment, space=request.space,
            data=ObjectWriteResult(technical_name=name, object_type=request.object_type,
                                   definition=payload, operation=operation))
