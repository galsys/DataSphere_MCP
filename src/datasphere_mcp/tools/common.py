import asyncio
import time

from pydantic import ValidationError

from ..exceptions import DatasphereError, OperationTimeout
from ..logging import audit
from ..models.common import Result, Risk, SafeError
from ..runtime import Runtime


READ_METADATA = {
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
                    "openWorldHint": True},
    "tags": {"READ"}, "meta": {"risk": "READ"},
}

WRITE_METADATA = {
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
                    "openWorldHint": True},
    "tags": {"WRITE"}, "meta": {"risk": "WRITE"},
}

DESTRUCTIVE_METADATA = {
    "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False,
                    "openWorldHint": True},
    "tags": {"DESTRUCTIVE"}, "meta": {"risk": "DESTRUCTIVE"},
}


async def invoke(runtime: Runtime, tool: str, context: dict, operation, response_model: type[Result],
                 risk: Risk = Risk.READ):
    started = time.monotonic()
    code = None
    try:
        async with asyncio.timeout(runtime.settings.operation_timeout):
            result = await operation()
        if runtime.settings.mock_mode:
            result.warnings.append("MOCK MODE: synthetic fixtures, not a live Datasphere response.")
        return response_model.model_validate(runtime.redactor.clean(result.model_dump(mode="json")))
    except DatasphereError as exc:
        code, message = exc.code, exc.message
    except ValidationError:
        code, message = "VALIDATION_ERROR", "Invalid environment, identifier, object type or limit."
    except TimeoutError:
        code, message = OperationTimeout.code, OperationTimeout.message
    except asyncio.CancelledError:
        code = "OPERATION_CANCELLED"
        raise
    except Exception:
        code, message = "INTERNAL_ERROR", "The operation failed safely; inspect server configuration and tests."
    finally:
        audit(tool, runtime.redactor.clean(context), time.monotonic() - started, code is None, code, risk)
    return response_model(success=False, environment=context.get("environment"),
                          error=SafeError(code=code, message=message))
