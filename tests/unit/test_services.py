import pytest

from datasphere_mcp.adapters.mock import MockAdapter
from datasphere_mcp.exceptions import ObjectNotFoundError, ResponseFormatError, UnsupportedCapability
from datasphere_mcp.models.common import Environment, Page
from datasphere_mcp.models.dependencies import DependencyRequest, Direction
from datasphere_mcp.models.objects import ObjectListRequest, ObjectRequest
from datasphere_mcp.models.writes import ObjectDeleteRequest
from datasphere_mcp.services.csn import references
from datasphere_mcp.services.dependency_service import DependencyService
from datasphere_mcp.services.object_service import ObjectService
from datasphere_mcp.services.space_service import SpaceService
from datasphere_mcp.services.write_service import WriteService


async def test_spaces_and_object_pagination():
    adapter = MockAdapter()
    spaces = await SpaceService(adapter).list_spaces(Environment.DEV, Page())
    assert spaces.data.items[0].space == "BSG_BI"
    objects = ObjectService(adapter)
    first = await objects.list_objects(ObjectListRequest(environment="DEV", space="BSG_BI", object_type="views", limit=1))
    assert first.data.next_offset == 1
    second = await objects.list_objects(ObjectListRequest(environment="DEV", space="BSG_BI", object_type="views", limit=1, offset=1))
    assert second.data.items == [] and second.data.next_offset is None
    with pytest.raises(ObjectNotFoundError):
        await objects.get_object(ObjectRequest(environment="DEV", space="BSG_BI", object_type="views", technical_name="MISSING"))


def test_csn_join_subquery_and_association_not_column_refs():
    definition = {"query": {"SELECT": {"from": {"join": "inner", "args": [
        {"ref": ["A"], "as": "a"}, {"SELECT": {"from": {"ref": [{"id": "B"}]}}}]},
        "columns": [{"ref": ["a", "ID"]}, {"val": {"from": {"ref": ["FAKE"]}}}]}},
        "elements": {"assoc": {"type": "cds.Association", "target": "C"}},
        "editorSettings": {"from": {"ref": ["WRONG"]}}}
    assert {r[0] for r in references(definition)} == {"A", "B", "C"}


async def test_transitive_dependencies_and_cycles(settings):
    adapter = MockAdapter()
    # A cycle must terminate and the edge still remains visible.
    adapter.objects[("local-tables", "T_TEST")]["definitions"]["T_TEST"]["elements"]["back"] = {
        "type": "cds.Association", "target": "V_TEST"}
    service = DependencyService(ObjectService(adapter), settings)
    result = await service.get_dependencies(DependencyRequest(environment="DEV", space="BSG_BI",
        object_type="analytic-models", technical_name="AM_TEST"))
    assert len(result.data.nodes) == 3
    assert len(result.data.edges) == 3
    assert not result.data.complete
    assert all(e.evidence for e in result.data.edges)


async def test_depth_limit_and_unknown_reference(settings):
    adapter = MockAdapter()
    service = DependencyService(ObjectService(adapter), settings)
    result = await service.get_dependencies(DependencyRequest(environment="DEV", space="BSG_BI",
        object_type="analytic-models", technical_name="AM_TEST", max_depth=1))
    assert result.data.truncated
    adapter.objects[("views", "V_TEST")]["definitions"]["V_TEST"]["query"]["SELECT"]["from"] = {"ref": ["EXTERNAL"]}
    result = await service.get_dependencies(DependencyRequest(environment="DEV", space="BSG_BI",
        object_type="views", technical_name="V_TEST"))
    assert not result.data.nodes[1].resolved
    assert result.data.nodes[1].object_type is None


async def test_unsupported_direction_and_format(settings):
    adapter = MockAdapter()
    service = DependencyService(ObjectService(adapter), settings)
    request = DependencyRequest(environment="DEV", space="BSG_BI", object_type="local-tables", technical_name="T_TEST", direction="BOTH")
    with pytest.raises(UnsupportedCapability):
        await service.get_dependencies(request)
    request.direction = Direction.UPSTREAM
    adapter.objects[("local-tables", "T_TEST")] = {"unknown": {}}
    with pytest.raises(UnsupportedCapability):
        await service.get_dependencies(request)


async def test_unrecognized_list_is_not_empty_success():
    adapter = MockAdapter()
    async def bad(request):
        return {"unrecognized": []}
    adapter.list_objects = bad
    with pytest.raises(ResponseFormatError):
        await ObjectService(adapter).list_objects(ObjectListRequest(environment="DEV", space="BSG_BI", object_type="views"))


async def test_delete_service_removes_object(settings):
    settings.dev.allow_delete = True
    adapter = MockAdapter()
    service = WriteService(adapter, settings)
    request = ObjectDeleteRequest(environment="DEV", space="BSG_BI", object_type="local-tables",
                                  technical_name="T_TEST", confirmed=True)
    result = await service.delete_object(request)
    assert result.data.deleted and result.data.operation == "delete"
    with pytest.raises(ObjectNotFoundError):
        await adapter.read_object(ObjectRequest(environment="DEV", space="BSG_BI",
                                                object_type="local-tables", technical_name="T_TEST"))
    with pytest.raises(ObjectNotFoundError):
        await service.delete_object(request)
