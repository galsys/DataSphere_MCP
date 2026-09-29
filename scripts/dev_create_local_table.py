"""Create and verify the fixed DEV acceptance local table through MCP."""
import asyncio
import json
from pathlib import Path

from fastmcp import Client

from datasphere_mcp.config import Settings
from datasphere_mcp.server import create_server


ENVIRONMENT = "DEV"
SPACE = "BSG_BI"
OBJECT_TYPE = "local-tables"
TECHNICAL_NAME = "T_LCH_KING01"
CSN_PATH = Path(__file__).parents[1] / "docs" / "csn" / f"{TECHNICAL_NAME}.csn.json"


async def main() -> int:
    settings = Settings(_env_file=".env")
    if settings.mock_mode or not settings.dev.allow_write:
        print(json.dumps({"success": False, "error": "DEV_WRITE_NOT_ENABLED"}))
        return 2
    definition = json.loads(CSN_PATH.read_text(encoding="utf-8"))
    args = {"environment": ENVIRONMENT, "space": SPACE, "object_type": OBJECT_TYPE,
            "technical_name": TECHNICAL_NAME}
    async with Client(create_server(settings)) as client:
        existing = await client.call_tool("get_object", args, raise_on_error=False)
        existing_body = existing.structured_content or {}
        if existing_body.get("success"):
            listed = await client.call_tool("list_objects", {
                "environment": ENVIRONMENT, "space": SPACE, "object_type": OBJECT_TYPE,
            }, raise_on_error=False)
            listed_body = listed.structured_content or {}
            found = any(row.get("technical_name") == TECHNICAL_NAME
                        for row in (listed_body.get("data") or {}).get("items", []))
            definition = (existing_body.get("data") or {}).get("definition") or {}
            entity = (definition.get("definitions") or {}).get(TECHNICAL_NAME) or {}
            report = {"success": bool(found), "created": False,
                      "already_existed": True, "verified_by_get_object": True,
                      "verified_by_list_objects": found, "environment": ENVIRONMENT,
                      "space": SPACE, "object_type": OBJECT_TYPE,
                      "technical_name": TECHNICAL_NAME,
                      "verified_elements": sorted((entity.get("elements") or {}).keys())}
            print(json.dumps(report))
            return 0 if report["success"] else 1
        created = await client.call_tool("create_object", {
            "environment": ENVIRONMENT, "space": SPACE, "object_type": OBJECT_TYPE,
            "definition": definition,
        }, raise_on_error=False)
        created_body = created.structured_content or {}
        if created.is_error or not created_body.get("success"):
            print(json.dumps({"success": False, "step": "create_object",
                              "error": created_body.get("error", {"code": "MCP_ERROR"})}))
            return 1
        verified = await client.call_tool("get_object", args, raise_on_error=False)
        verified_body = verified.structured_content or {}
        listed = await client.call_tool("list_objects", {
            "environment": ENVIRONMENT, "space": SPACE, "object_type": OBJECT_TYPE,
        }, raise_on_error=False)
        listed_body = listed.structured_content or {}
        found = any(row.get("technical_name") == TECHNICAL_NAME
                    for row in (listed_body.get("data") or {}).get("items", []))
        report = {
            "success": bool(verified_body.get("success") and found),
            "created": True,
            "verified_by_get_object": bool(verified_body.get("success")),
            "verified_by_list_objects": found,
            "environment": ENVIRONMENT,
            "space": SPACE,
            "object_type": OBJECT_TYPE,
            "technical_name": TECHNICAL_NAME,
        }
        print(json.dumps(report))
        return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
