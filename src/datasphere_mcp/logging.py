import json
import logging
import sys
from datetime import UTC, datetime


logger = logging.getLogger("datasphere_mcp.audit")


def configure_logging():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # HTTP URLs, headers and library exceptions must not enter server logs.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def audit(tool: str, context: dict, duration: float, success: bool, code: str | None, risk="READ"):
    logger.info(json.dumps({
        "timestamp": datetime.now(UTC).isoformat(), "tool": tool, "operation": tool,
        "risk": str(risk), "duration_ms": round(duration * 1000), "success": success,
        "error_code": code, **context,
    }, ensure_ascii=True))
