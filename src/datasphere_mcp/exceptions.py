"""Exceptions contain fixed, public-safe text, never upstream messages."""


class DatasphereError(Exception):
    code = "DATASPHERE_ERROR"
    message = "Datasphere operation failed."

    def __init__(self):
        super().__init__(self.message)


class ConfigurationError(DatasphereError):
    code = "CONFIGURATION_ERROR"
    message = "Check server-side environment, HTTPS URLs, credentials and CLI configuration."


class AuthenticationError(DatasphereError):
    code = "AUTHENTICATION_ERROR"
    message = "OAuth authentication failed. Renew the server-side user session or credentials."


class AuthorizationError(DatasphereError):
    code = "AUTHORIZATION_ERROR"
    message = "The configured identity lacks permission for this Datasphere operation."


class ObjectNotFoundError(DatasphereError):
    code = "OBJECT_NOT_FOUND"
    message = "Datasphere object was not found."


class CLIExecutionError(DatasphereError):
    code = "CLI_EXECUTION_ERROR"
    message = "SAP CLI failed. Check tenant command support and identity permissions locally."


class APIError(DatasphereError):
    code = "API_ERROR"
    message = "SAP API request failed."


class ResponseFormatError(DatasphereError):
    code = "RESPONSE_FORMAT_ERROR"
    message = "Unsupported SAP response format; a sanitized tenant fixture is required."


class OperationTimeout(DatasphereError):
    code = "OPERATION_TIMEOUT"
    message = "Datasphere operation exceeded its time limit."


class ResponseTooLarge(DatasphereError):
    code = "RESPONSE_TOO_LARGE"
    message = "SAP response exceeded the configured size limit."


class PolicyViolationError(DatasphereError):
    code = "POLICY_VIOLATION"
    message = "Only READ operations are enabled in this release."


class ConfirmationRequiredError(DatasphereError):
    code = "CONFIRMATION_REQUIRED"
    message = "Explicit confirmation is required for this environment write operation."


class UnsupportedCapability(DatasphereError):
    code = "UNSUPPORTED_CAPABILITY"
    message = "This capability is not verified for the selected backend or object format."
