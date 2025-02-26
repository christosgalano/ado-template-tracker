"""Core subpackage for Azure DevOps pipeline template tracking.

This subpackage provides the core components for tracking template adoption
in Azure DevOps pipelines. It handles API interactions, data models, compliance
evaluation, and adoption metrics collection.

Modules:
    adoption: Template adoption tracking logic and compliance assessment
    client: Azure DevOps API client with sync/async support
    models: Data models for resources, configuration, and tracking
    exceptions: Error types and hierarchies for graceful error handling

Components:
    API Client:
        AzureDevOpsClient: Handles API interactions with Azure DevOps

    Adoption Tracking:
        TemplateAdoptionTracker: Orchestrates the template tracking process

    Configuration:
        AdoptionTarget: Defines where to look for template adoption
        TemplateSource: Defines source templates to track
        ComplianceMode: Determines how compliance is evaluated (ANY/MAJORITY/ALL)
        ViewMode: Controls results presentation format
        TargetScope: Determines analysis scope level

    Resource Models:
        Template: Represents a reusable template
        Pipeline: Represents an Azure DevOps pipeline
        Project: Represents an Azure DevOps project
        Repository: Represents an Azure DevOps git repository
        Organization: Represents an Azure DevOps organization

Example:
    Basic usage tracking template adoption:

    >>> from ado_template_tracker.core import (
    ...     AzureDevOpsClient,
    ...     TemplateAdoptionTracker,
    ...     AdoptionTarget,
    ...     TemplateSource,
    ...     ComplianceMode
    ... )
    >>>
    >>> async def track_templates():
    ...     async with AzureDevOpsClient("organization") as client:
    ...         tracker = TemplateAdoptionTracker(
    ...             client=client,
    ...             target=AdoptionTarget(
    ...                 organization="MyOrg",
    ...                 project="MyProject"
    ...             ),
    ...             source=TemplateSource(
    ...                 project="Templates",
    ...                 repository="PipelineTemplates"
    ...             ),
    ...             compliance_mode=ComplianceMode.MAJORITY
    ...         )
    ...         result, metrics = await tracker.track()
    ...         print(f"Adoption rate: {result.pipeline_adoption_rate:.2f}%")
"""

from ado_template_tracker.core.adoption import TemplateAdoptionTracker
from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.exceptions import (
    ADOTemplateTrackerError,
    AuthenticationError,
    ConfigurationError,
    InitializationError,
    InvalidComplianceModeError,
    InvalidViewModeError,
    SchemaFetchError,
)
from ado_template_tracker.core.models import (
    Adoption,
    AdoptionMetrics,
    AdoptionTarget,
    ComplianceMode,
    Organization,
    Pipeline,
    Project,
    Repository,
    TargetScope,
    Template,
    TemplateSource,
    UsageType,
    ViewMode,
)

__all__ = [  # noqa: RUF022
    # Main components
    "AzureDevOpsClient",
    "TemplateAdoptionTracker",
    # Resource models
    "Adoption",
    "AdoptionMetrics",
    "Organization",
    "Pipeline",
    "Project",
    "Repository",
    "Template",
    # Configuration models
    "AdoptionTarget",
    "ComplianceMode",
    "TargetScope",
    "TemplateSource",
    "UsageType",
    "ViewMode",
    # Exceptions
    "ADOTemplateTrackerError",
    "AuthenticationError",
    "ConfigurationError",
    "InitializationError",
    "InvalidComplianceModeError",
    "InvalidViewModeError",
    "SchemaFetchError",
]
