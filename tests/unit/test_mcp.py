import json
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import pytest

from datasphere_mcp.config import Settings
from datasphere_mcp.server import create_server


async def test_full_mcp_workflow_and_schema(settings):
    async with Client(create_server(settings)) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == {"list_spaces", "list_objects", "get_object", "get_dependencies",
                                           "get_task_status", "get_task_log", "create_object", "update_object",
                                           "delete_object"}
        for tool in tools:
            if tool.name in {"create_object", "update_object", "delete_object"}:
                assert not tool.annotations.read_only_hint
            else:
                assert tool.annotations.read_only_hint
            if tool.name == "delete_object":
                assert tool.annotations.destructive_hint
            assert "environment" in tool.input_schema["required"]
            assert "secret" not in json.dumps(tool.input_schema).lower()
        args = {"environment": "DEV", "space": "BSG_BI", "object_type": "local-tables", "technical_name": "T_TEST"}
        spaces = await client.call_tool("list_spaces", {"environment": "DEV"})
        assert spaces.structured_content["data"]["items"][0]["space"] == "BSG_BI"
        listed = await client.call_tool("list_objects", {k: v for k, v in args.items() if k != "technical_name"})
        assert listed.structured_content["data"]["items"][0]["technical_name"] == "T_TEST"
        definition = await client.call_tool("get_object", args)
        assert "T_TEST" in definition.structured_content["data"]["definition"]["definitions"]
        graph = await client.call_tool("get_dependencies", args)
        assert graph.structured_content["data"]["edges"] == []
        assert graph.structured_content["warnings"]
        status = await client.call_tool("get_task_status", {"environment": "DEV", "space": "BSG_BI", "log_id": "LOG_TEST"})
        assert status.structured_content["data"]["status"] == "SUCCEEDED"
        log = await client.call_tool("get_task_log", {"environment": "DEV", "space": "BSG_BI", "log_id": "LOG_TEST"})
        assert log.structured_content["data"]["log_id"] == "LOG_TEST"

        settings.dev.allow_write = True
        created = await client.call_tool("create_object", {
            "environment": "DEV", "space": "BSG_BI", "object_type": "views",
            "definition": {"technicalName": "V_CREATED", "definitions": {"V_CREATED": {"kind": "entity"}}},
        })
        assert created.structured_content["data"]["technical_name"] == "V_CREATED"
        updated = await client.call_tool("update_object", {
            "environment": "DEV", "space": "BSG_BI", "object_type": "views",
            "technical_name": "V_CREATED", "definition": {"kind": "entity", "updated": True},
        })
        assert updated.structured_content["data"]["operation"] == "update"
        settings.qas.allow_write = True
        guarded = await client.call_tool("create_object", {
            "environment": "QAS", "space": "BSG_BI", "object_type": "views",
            "definition": {"kind": "entity"},
        })
        assert guarded.structured_content["error"]["code"] == "CONFIRMATION_REQUIRED"
        settings.dev.allow_delete = True
        unconfirmed_delete = await client.call_tool("delete_object", args)
        assert unconfirmed_delete.structured_content["error"]["code"] == "CONFIRMATION_REQUIRED"
        deleted = await client.call_tool("delete_object", {**args, "confirmed": True})
        assert deleted.structured_content["data"] == {
            "technical_name": "T_TEST", "object_type": "local-tables",
            "deleted": True, "operation": "delete",
        }
        deleted_object = await client.call_tool("get_object", args)
        assert deleted_object.structured_content["error"]["code"] == "OBJECT_NOT_FOUND"
        failure = await client.call_tool("get_object", {**args, "technical_name": "MISSING"})
        assert failure.structured_content["error"]["code"] == "OBJECT_NOT_FOUND"
        unsupported = await client.call_tool("get_dependencies", {**args, "direction": "DOWNSTREAM"})
        assert unsupported.structured_content["error"]["code"] == "UNSUPPORTED_CAPABILITY"


async def test_mcp_rejects_bad_input(settings):
    async with Client(create_server(settings)) as client:
        for args in ({}, {"environment": "UNKNOWN"}, {"environment": "DEV", "limit": 999}):
            result = await client.call_tool("list_spaces", args, raise_on_error=False)
            assert result.is_error
        result = await client.call_tool("list_objects", {"environment": "DEV", "space": "REJECTED;SECRET",
                                        "object_type": "local-tables"}, raise_on_error=False)
        assert result.is_error
        assert "REJECTED;SECRET" not in str(result.content)


async def test_mcp_response_redacts_credentials(settings, monkeypatch):
    from pydantic import SecretStr
    from datasphere_mcp.adapters.mock import MockAdapter
    settings.dev.client_secret = SecretStr("should-never-escape")
    original = MockAdapter.read_object
    async def read(self, request):
        result = await original(self, request)
        result["debug"] = "upstream echoed should-never-escape"
        return result
    monkeypatch.setattr(MockAdapter, "read_object", read)
    async with Client(create_server(settings)) as client:
        result = await client.call_tool("get_object", {"environment": "DEV", "space": "BSG_BI",
                                       "object_type": "local-tables", "technical_name": "T_TEST"})
        assert "should-never-escape" not in json.dumps(result.structured_content)
        assert "[REDACTED]" in json.dumps(result.structured_content)


async def test_unconfigured_environment_is_safe():
    async with Client(create_server(Settings(_env_file=None))) as client:
        result = await client.call_tool("list_spaces", {"environment": "DEV"})
        assert result.structured_content["error"]["code"] == "CONFIGURATION_ERROR"


async def test_stdio_transport(tmp_path):
    # Real subprocess exercises startup, MCP handshake, stdout discipline and shutdown.
    transport = StdioTransport(command=sys.executable, args=["-m", "datasphere_mcp.server"],
                               env={"DSP_MOCK_MODE": "true", "DSP_ENV_FILE": str(tmp_path / "absent.env")})
    async with Client(transport) as client:
        result = await client.call_tool("list_spaces", {"environment": "DEV"})
        assert result.structured_content["success"]
