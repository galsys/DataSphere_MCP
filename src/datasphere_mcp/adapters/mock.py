from copy import deepcopy

from ..exceptions import ObjectNotFoundError
from ..models.objects import ObjectListRequest, ObjectRequest
from ..models.tasks import TaskLogRequest
from ..models.writes import ObjectWriteRequest


def fixtures():
    return {
        ("local-tables", "T_TEST"): {"definitions": {"T_TEST": {
            "kind": "entity", "@EndUserText.label": "Test table",
            "elements": {"ID": {"type": "cds.Integer", "key": True}},
        }}},
        ("views", "V_TEST"): {"definitions": {"V_TEST": {
            "kind": "entity", "query": {"SELECT": {"from": {"ref": ["T_TEST"]}}},
        }}},
        # Synthetic CSN fixture, not a captured SAP Analytic Model payload.
        ("analytic-models", "AM_TEST"): {"definitions": {"AM_TEST": {
            "kind": "entity", "query": {"SELECT": {"from": {"ref": ["V_TEST"]}}},
        }}},
    }


class MockAdapter:
    def __init__(self):
        self.objects = fixtures()

    async def list_spaces(self):
        return [{"spaceId": "BSG_BI", "businessName": "Mock BI"}]

    async def list_objects(self, request: ObjectListRequest):
        if request.space != "BSG_BI":
            raise ObjectNotFoundError()
        items = [{"technicalName": name} for kind, name in self.objects if kind == request.object_type]
        return deepcopy(items[request.offset:request.offset + request.limit])

    async def read_object(self, request: ObjectRequest):
        if request.space != "BSG_BI":
            raise ObjectNotFoundError()
        try:
            return deepcopy(self.objects[(request.object_type, request.technical_name)])
        except KeyError:
            raise ObjectNotFoundError() from None

    async def get_task_log(self, request: TaskLogRequest, info_level: str):
        if request.space != "BSG_BI" or request.log_id != "LOG_TEST":
            raise ObjectNotFoundError()
        if info_level == "status":
            return {"logId": request.log_id, "status": "SUCCEEDED"}
        return {"logId": request.log_id, "status": "SUCCEEDED", "message": "Mock task completed"}

    async def create_object(self, request: ObjectWriteRequest):
        name = request.technical_name or request.definition.get("technicalName")
        if not isinstance(name, str):
            name = "MOCK_CREATED"
        key = (request.object_type.value, name)
        if key in self.objects:
            raise ObjectNotFoundError()
        self.objects[key] = deepcopy(request.definition)
        return {"technicalName": name, **deepcopy(request.definition)}

    async def update_object(self, request: ObjectWriteRequest):
        if not request.technical_name:
            raise ObjectNotFoundError()
        key = (request.object_type.value, request.technical_name)
        if key not in self.objects:
            raise ObjectNotFoundError()
        self.objects[key] = deepcopy(request.definition)
        return {"technicalName": request.technical_name, **deepcopy(request.definition)}
