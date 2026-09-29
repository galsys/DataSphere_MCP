from dataclasses import dataclass

import httpx

from .adapters.cli import DatasphereCLIAdapter
from .adapters.mock import MockAdapter
from .adapters.odata import DatasphereODataAdapter
from .adapters.rest import DatasphereRESTAdapter
from .auth.oauth import OAuthProvider
from .config import Settings
from .models.common import Environment
from .security import SecretRedactor
from .services.dependency_service import DependencyService
from .services.object_service import ObjectService
from .services.space_service import SpaceService
from .services.task_service import TaskService
from .services.write_service import WriteService


@dataclass
class Services:
    spaces: SpaceService
    objects: ObjectService
    dependencies: DependencyService
    tasks: TaskService
    writes: WriteService


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.redactor = SecretRedactor()
        for env in Environment:
            cfg = getattr(settings, env.value.lower())
            for key in ("client_id", "client_secret", "refresh_token"):
                self.redactor.add(getattr(cfg, key).get_secret_value())
        self._services: dict[Environment, Services] = {}
        self._clients: list[httpx.AsyncClient] = []
        self._cli: list[DatasphereCLIAdapter] = []

    def services(self, environment: Environment) -> Services:
        environment = Environment(environment)
        if environment not in self._services:
            catalog = None
            if self.settings.mock_mode:
                adapter = MockAdapter()
            else:
                tenant = self.settings.tenant(environment)
                client = httpx.AsyncClient(verify=True, follow_redirects=False)
                self._clients.append(client)
                auth = OAuthProvider(tenant, client, self.redactor)
                adapter = DatasphereCLIAdapter(self.settings, tenant, auth)
                self._cli.append(adapter)
                if tenant.spaces_backend == "catalog":
                    catalog = DatasphereODataAdapter(DatasphereRESTAdapter(
                        tenant, auth, client, self.settings.max_response_bytes,
                    ))
            objects = ObjectService(adapter)
            self._services[environment] = Services(
                SpaceService(adapter, catalog), objects, DependencyService(objects, self.settings),
                TaskService(adapter), WriteService(adapter, self.settings),
            )
        return self._services[environment]

    async def close(self):
        for client in self._clients:
            await client.aclose()
        for adapter in self._cli:
            adapter.close()
        self._services.clear()
        self._clients.clear()
        self._cli.clear()
