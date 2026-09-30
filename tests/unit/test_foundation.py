import pytest
from pydantic import ValidationError

from datasphere_mcp.config import Settings, TenantConfig
from datasphere_mcp.exceptions import (
    ConfigurationError, ConfirmationRequiredError, PolicyViolationError,
)
from datasphere_mcp.models.common import Environment, Page, Risk
from datasphere_mcp.models.objects import ObjectRequest
from datasphere_mcp.security import SecretRedactor, authorize, authorize_delete


def test_nested_dotenv(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DSP_DEV_BASE_URL=https://dev.example\nDSP_DEV_CLIENT_SECRET=secret-value\nDSP_MOCK_MODE=true\n")
    cfg = Settings(_env_file=env)
    assert cfg.dev.base_url == "https://dev.example"
    assert cfg.dev.client_secret.get_secret_value() == "secret-value"
    assert cfg.mock_mode
    assert "secret-value" not in repr(cfg)
    with pytest.raises(ConfigurationError):
        cfg.tenant(Environment.PRD)


@pytest.mark.parametrize("name", ["--help", "../file", "X;whoami", "X|Y", "X\nY", "$(cmd)", "X/Y", ""])
def test_identifier_validation(name):
    with pytest.raises(ValidationError):
        ObjectRequest(environment="DEV", space="BSG_BI", object_type="local-tables", technical_name=name)


@pytest.mark.parametrize("url", ["http://dev.example", "https://user:pass@dev.example", "https://dev.example/path", "https://dev.example?q=x"])
def test_tenant_origin(url):
    with pytest.raises((ConfigurationError, ValidationError)):
        TenantConfig(base_url=url)


@pytest.mark.parametrize("env", list(Environment))
def test_read_only_policy(env):
    authorize(env)
    for risk in (Risk.WRITE, Risk.EXECUTE, Risk.DESTRUCTIVE):
        with pytest.raises(PolicyViolationError):
            authorize(env, risk)


def test_delete_policy(settings):
    with pytest.raises(PolicyViolationError):
        authorize_delete(settings, Environment.DEV, confirmed=True)
    settings.dev.allow_delete = True
    with pytest.raises(ConfirmationRequiredError):
        authorize_delete(settings, Environment.DEV, confirmed=False)
    authorize_delete(settings, Environment.DEV, confirmed=True)
    for environment in (Environment.QAS, Environment.PRD):
        getattr(settings, environment.value.lower()).allow_delete = True
        with pytest.raises(PolicyViolationError):
            authorize_delete(settings, environment, confirmed=True)


def test_limits():
    for values in ({"limit": 201}, {"offset": -1}, {"limit": True}):
        with pytest.raises(ValidationError):
            Page(**values)


def test_redaction():
    redactor = SecretRedactor()
    redactor.add("secret-value")
    payload = {"client_secret": "unknown", "x": "error secret-value", "nested": ["Bearer aaa.bbb.ccc"],
               "elements": {"ID": {"type": "cds.Integer"}}}
    clean = redactor.clean(payload)
    assert "secret-value" not in str(clean)
    assert "aaa.bbb.ccc" not in str(clean)
    assert clean["client_secret"] == "[REDACTED]"
    assert clean["elements"] == payload["elements"]
