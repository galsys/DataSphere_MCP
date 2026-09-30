import re
from typing import Any

from .config import Settings
from .exceptions import ConfirmationRequiredError, PolicyViolationError
from .models.common import Environment, Risk


def authorize(environment: Environment, risk: Risk = Risk.READ) -> None:
    Environment(environment)
    if risk != Risk.READ:
        raise PolicyViolationError()


def authorize_write(settings: Settings, environment: Environment, confirmed: bool) -> None:
    environment = Environment(environment)
    # Runtime configuration may intentionally omit a base URL in mock mode.
    tenant = getattr(settings, environment.value.lower())
    if environment == Environment.PRD or not tenant.allow_write:
        raise PolicyViolationError()
    if environment == Environment.QAS and not confirmed:
        raise ConfirmationRequiredError()


def authorize_delete(settings: Settings, environment: Environment, confirmed: bool) -> None:
    environment = Environment(environment)
    tenant = getattr(settings, environment.value.lower())
    # Initial policy permits guarded deletes only in DEV. Client input cannot
    # elevate QAS or PRD, even if their server-side flag is changed accidentally.
    if environment != Environment.DEV or not tenant.allow_delete:
        raise PolicyViolationError()
    if not confirmed:
        raise ConfirmationRequiredError()


class SecretRedactor:
    def __init__(self):
        self._values: set[str] = set()

    def add(self, value: str) -> None:
        if value:
            self._values.add(value)

    def clean(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                self.clean(str(k)): "[REDACTED]" if re.search(
                    r"(?i)(access.?token|refresh.?token|client.?secret|password|authorization)", str(k)
                ) else self.clean(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.clean(v) for v in value]
        if isinstance(value, str):
            for secret in sorted(self._values, key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
            return re.sub(r"(?i)\bBearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        return value
