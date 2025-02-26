"""Custom exceptions for template tracking.

This module defines the exception hierarchy used throughout the template tracking system.
It provides specialized exceptions for different types of errors that can occur during
template tracking operations, from authentication and configuration issues to API
and parsing errors.

Exception Categories:
    Authentication: Errors related to Azure DevOps authentication
    Configuration: Errors related to invalid configuration values or formats
    Initialization: Errors occurring during tracker or component setup
    API: Errors during API calls and content retrieval
    Parsing: Errors related to YAML processing

Exception Hierarchy:
    ADOTemplateTrackerError
    ├── AuthenticationError
    ├── InitializationError
    ├── ConfigurationError
    │   ├── InvalidClientError
    │   ├── SourceConfigurationError
    │   ├── TargetConfigurationError
    │   ├── TemplateConfigurationError
    │   ├── InvalidTemplatePathError
    │   ├── InvalidViewModeError
    │   └── InvalidComplianceModeError
    ├── TrackerNotInitializedError
    ├── APIError
    │   ├── SchemaFetchError
    │   └── ContentFetchError
    └── YAMLParsingError

Usage:
    ```python
    from ado_template_tracker.core.exceptions import (
        ADOTemplateTrackerError,
        AuthenticationError,
        ConfigurationError
    )

    try:
        # Code that might raise exceptions
        tracker.track()
    except AuthenticationError:
        # Handle authentication issues
        print("Authentication failed. Check your credentials.")
    except ConfigurationError as e:
        # Handle configuration issues
        print(f"Configuration error: {e}")
    except ADOTemplateTrackerError as e:
        # Handle any other tracker-specific errors
        print(f"Error occurred: {e}")
    ```

Note:
    All exceptions inherit from ADOTemplateTrackerError to allow catching
    all package-specific exceptions with a single except clause.
"""


class ADOTemplateTrackerError(Exception):
    """Base exception for ADO Template Tracker."""


class AuthenticationError(ADOTemplateTrackerError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Failed to authenticate with Azure DevOps") -> None:
        super().__init__(message)


class InitializationError(ADOTemplateTrackerError):
    """Raised when initialization fails."""

    def __init__(self, message: str = "Failed to initialize tracker") -> None:
        super().__init__(message)


class ConfigurationError(ADOTemplateTrackerError):
    """Base class for configuration related errors."""


class InvalidClientError(ConfigurationError):
    """Raised when an invalid client is provided."""

    def __init__(self, message: str = "Client must be an instance of AzureDevOpsClient") -> None:
        super().__init__(message)


class SourceConfigurationError(ConfigurationError):
    """Raised when source configuration is invalid."""

    def __init__(self, message: str = "Invalid source configuration") -> None:
        super().__init__(message)


class TargetConfigurationError(ConfigurationError):
    """Raised when target configuration is invalid."""

    def __init__(self, message: str = "Target scope is invalid") -> None:
        super().__init__(message)


class TemplateConfigurationError(ConfigurationError):
    """Raised when template configuration is invalid."""

    def __init__(self, message: str = "Template configuration invalid") -> None:
        super().__init__(message)


class InvalidTemplatePathError(ConfigurationError):
    """Raised when template path is invalid."""

    def __init__(self, valid_extensions: tuple[str, ...]) -> None:
        super().__init__(
            f"Template path must end with one of: {', '.join(valid_extensions)}",
        )


class InvalidViewModeError(ConfigurationError):
    """Raised when view mode is invalid."""

    def __init__(self, message: str = "Invalid view mode") -> None:
        super().__init__(message)


class InvalidComplianceModeError(ConfigurationError):
    """Raised when compliance mode is invalid."""

    def __init__(self, message: str = "Invalid compliance mode") -> None:
        super().__init__(message)


class TrackerNotInitializedError(ADOTemplateTrackerError):
    """Raised when tracker is used before initialization."""

    def __init__(self) -> None:
        super().__init__("Tracker not initialized. Call 'setup()' first.")


class APIError(ADOTemplateTrackerError):
    """Base class for API related errors."""


class SchemaFetchError(APIError):
    """Raised when fetching pipeline schema fails."""

    def __init__(self) -> None:
        super().__init__("Failed to fetch schema from GitHub")


class ContentFetchError(APIError):
    """Raised when fetching content fails."""

    def __init__(self) -> None:
        super().__init__("Failed to get pipeline content")


class YAMLParsingError(ADOTemplateTrackerError):
    """Raised when YAML parsing fails."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Error parsing YAML in {path}")
