import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from datasphere_mcp.adapters.cli import DatasphereCLIAdapter
from datasphere_mcp.config import TenantConfig
from datasphere_mcp.exceptions import CLIExecutionError, OperationTimeout, ResponseTooLarge
from datasphere_mcp.models.objects import ObjectListRequest, ObjectRequest
from datasphere_mcp.models.writes import ObjectDeleteRequest, ObjectWriteRequest


class Process:
    def __init__(self, stdout=b"", stderr=b"", code=0):
        self.stdout, self.stderr = asyncio.StreamReader(), asyncio.StreamReader()
        for stream, data in ((self.stdout, stdout), (self.stderr, stderr)):
            stream.feed_data(data)
            stream.feed_eof()
        self.returncode = code
        self.killed = False

    async def wait(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.stdout.feed_eof()
        self.stderr.feed_eof()


def adapter(settings, tmp_path, monkeypatch):
    entry = tmp_path / "terminal.js"
    entry.write_text("")
    settings.cli_entry = entry
    monkeypatch.setattr("datasphere_mcp.adapters.cli.shutil.which", lambda _: "node.exe")
    auth = AsyncMock()
    auth.get_token.return_value = "access-secret"
    return DatasphereCLIAdapter(settings, TenantConfig(base_url="https://dev.example"), auth)


async def test_commands_and_secret_isolation(settings, tmp_path, monkeypatch):
    cli = adapter(settings, tmp_path, monkeypatch)
    calls = []
    monkeypatch.setenv("NODE_TLS_REJECT_UNAUTHORIZED", "0")
    monkeypatch.setenv("CLIENT_SECRET", "wrong-env-secret")
    async def spawn(*args, **kwargs):
        calls.append((args, kwargs))
        assert "access-secret" not in str(args)
        assert "shell" not in kwargs
        assert kwargs["env"]["ACCESS_TOKEN"] == "access-secret"
        assert "CLIENT_SECRET" not in kwargs["env"]
        assert "NODE_TLS_REJECT_UNAUTHORIZED" not in kwargs["env"]
        assert kwargs["stdin"] == asyncio.subprocess.DEVNULL
        if "--output" in args:
            Path(args[args.index("--output") + 1]).write_text('{"definitions":{"T_TEST":{"kind":"entity"}}}')
        return Process()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    try:
        await cli.list_spaces()
        await cli.list_objects(ObjectListRequest(environment="DEV", space="BSG_BI", object_type="local-tables", limit=7, offset=14))
        await cli.read_object(ObjectRequest(environment="DEV", space="BSG_BI", object_type="local-tables", technical_name="T_TEST"))
        await cli.create_object(ObjectWriteRequest(environment="DEV", space="BSG_BI", object_type="views",
                                                   definition={"definitions": {"V_CREATED": {"kind": "entity"}}}))
        await cli.update_object(ObjectWriteRequest(environment="DEV", space="BSG_BI", object_type="views",
                                                   technical_name="V_TEST", definition={"kind": "entity"}))
        await cli.delete_object(ObjectDeleteRequest(environment="DEV", space="BSG_BI",
                                                    object_type="local-tables", technical_name="T_TEST",
                                                    confirmed=True))
        assert calls[0][0][2:5] == ("config", "cache", "init")
        assert calls[1][0][2:4] == ("spaces", "list")
        assert calls[3][0][2:11] == ("objects", "local-tables", "list", "--space", "BSG_BI", "--top", "7", "--skip", "14")
        assert calls[5][0][2:9] == ("objects", "local-tables", "read", "--space", "BSG_BI", "--technical-name", "T_TEST")
        assert calls[7][0][2:7] == ("objects", "views", "create", "--space", "BSG_BI")
        assert "--file-path" in calls[7][0]
        assert "--output" not in calls[7][0]
        assert calls[9][0][2:9] == ("objects", "views", "read", "--space", "BSG_BI", "--technical-name", "V_CREATED")
        assert calls[11][0][2:9] == ("objects", "views", "update", "--space", "BSG_BI", "--technical-name", "V_TEST")
        assert "--file-path" in calls[11][0]
        assert "--output" not in calls[11][0]
        assert calls[13][0][2:9] == ("objects", "views", "read", "--space", "BSG_BI", "--technical-name", "V_TEST")
        assert calls[15][0][2:10] == ("objects", "local-tables", "delete", "--space", "BSG_BI",
                                      "--technical-name", "T_TEST", "--force")
        assert "--delete-anyway" not in calls[15][0]
        assert "--output" not in calls[15][0]
        assert not Path(calls[0][1]["cwd"]).exists()
        assert calls[0][1]["env"]["USERPROFILE"] == calls[1][1]["env"]["USERPROFILE"]
        assert calls[0][1]["env"]["USERPROFILE"] != calls[2][1]["env"]["USERPROFILE"]
    finally:
        cli.close()


async def test_timeout_kills_process(settings, tmp_path, monkeypatch):
    settings.cli_timeout = 0.01
    cli = adapter(settings, tmp_path, monkeypatch)
    proc = Process()
    proc.returncode = None
    proc.stdout = asyncio.StreamReader()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))
    try:
        with pytest.raises(OperationTimeout):
            await cli.list_spaces()
        assert proc.killed
    finally:
        cli.close()


async def test_cli_error_does_not_leak(settings, tmp_path, monkeypatch):
    cli = adapter(settings, tmp_path, monkeypatch)
    spawn = AsyncMock(return_value=Process(stderr=b"access-secret", code=1))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    try:
        with pytest.raises(CLIExecutionError) as error:
            await cli.list_spaces()
        assert "access-secret" not in str(error.value)
        # Failed discovery must stop before any object/space command is attempted.
        assert spawn.await_count == 1
        assert spawn.call_args.args[2:5] == ("config", "cache", "init")
    finally:
        cli.close()


async def test_response_limit(settings, tmp_path, monkeypatch):
    cli = adapter(settings, tmp_path, monkeypatch)
    settings.max_response_bytes = 1024
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=Process(stdout=b"x" * 2048)))
    try:
        with pytest.raises(ResponseTooLarge):
            await cli.list_spaces()
    finally:
        cli.close()
