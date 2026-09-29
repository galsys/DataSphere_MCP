import os
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .config import Settings
from .logging import configure_logging
from .runtime import Runtime
from .tools import dependencies, objects, spaces, tasks, writes
from .tools.middleware import SafeValidationMiddleware


def create_server(settings: Settings | None = None) -> FastMCP:
    runtime = Runtime(settings or Settings(_env_file=os.getenv("DSP_ENV_FILE", ".env")))

    @asynccontextmanager
    async def lifespan(server):
        try:
            yield {}
        finally:
            await runtime.close()

    mcp = FastMCP("datasphere-mcp", version="0.1.0", lifespan=lifespan,
                  middleware=[SafeValidationMiddleware()],
                  mask_error_details=True, strict_input_validation=False,
                  instructions="Read-only SAP Datasphere. Always select an environment explicitly. "
                               "Dependency results are partial CSN evidence, not complete lineage.")
    spaces.register(mcp, runtime)
    objects.register(mcp, runtime)
    dependencies.register(mcp, runtime)
    tasks.register(mcp, runtime)
    writes.register(mcp, runtime)
    return mcp


def main():
    configure_logging()
    try:
        server = create_server()
    except Exception:
        print("Invalid Datasphere server configuration. Check .env locally.", file=sys.stderr)
        raise SystemExit(2) from None
    server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
