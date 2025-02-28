"""Core data models for template adoption tracking.

This module defines the data models used throughout the template tracking system,
representing both Azure DevOps resources and template adoption metrics. These
models form the foundation of the data flow from source templates to adoption
analysis across projects, repositories, and pipelines.

Classes:
    Azure DevOps Resources:
        Template: Represents a template used in a pipeline
        Pipeline: Represents an Azure DevOps pipeline definition
        Repository: Represents an Azure DevOps git repository
        Project: Represents an Azure DevOps project
        Organization: Represents an Azure DevOps organization

    Configuration Models:
        TemplateSource: Configures which templates to track and validate
        AdoptionTarget: Configures where to look for template adoption
        TargetScope: Enum for determining analysis scope (org/project/repo/pipeline)
        ComplianceMode: Enum for compliance determination (any/majority/all)
        ViewMode: Enum for result presentation format

    Tracking Models:
        Adoption: Records template usage within a specific pipeline
        AdoptionMetrics: Collects and analyzes adoption statistics
        UsageType: Enum for template usage patterns (extend/include)

Example:
    ```python
    from ado_template_tracker.core.models import (
        AdoptionTarget,
        TemplateSource,
        Template,
        ComplianceMode,
    )

    # Configure template source to track
    source = TemplateSource(
        project="template-project",
        repository="template-repo",
        directories=["/templates", "/pipelines/templates"]
    )

    # Configure adoption target scope
    target = AdoptionTarget(
        organization="my-organization",
        project="target-project",
        repository="target-repo"
    )

    # Set compliance requirements
    compliance = ComplianceMode.MAJORITY

    # Create template instance for reference
    template = Template(
        name="build-template",
        path="templates/build.yml",
        repository="template-repo",
        project="template-project"
    )
    ```

Raises:
    InvalidTemplatePathError: When a template path doesn't match valid extensions
    TemplateConfigurationError: When template source configuration is invalid
    InvalidComplianceModeError: When an invalid compliance mode is specified
    InvalidViewModeError: When an invalid view mode is specified
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar

import yaml

from .exceptions import (
    InvalidComplianceModeError,
    InvalidTemplatePathError,
    InvalidViewModeError,
    SourceConfigurationError,
)


@dataclass(frozen=False)
class TemplateSource:
    """
    Represents the source templates to track for adoption. Can be either specific templates or all templates within directories.

    Attributes:
        project: Name of the Azure DevOps project containing templates
        repository: Name of the repository containing templates
        branch: Branch containing the templates (e.g., 'main', 'master'), defaults to 'main'
        template_path: Optional specific template to track
        directories: Optional list of directories containing templates to track, defaults to ['/']
        templates: List of all templates to track
        template_schema: Schema for the template configuration
    """  # noqa: E501

    project: str
    repository: str
    branch: str = "main"
    template_path: str | None = None
    directories: list[str] = field(default_factory=lambda: ["/"])
    templates: list[str] = field(default_factory=list)
    template_schema: dict[str, Any] = field(default_factory=dict)

    VALID_EXTENSIONS = (".yml", ".yaml")

    def __post_init__(self) -> None:
        """Validates and initializes the template source configuration."""
        if self.template_path and self.directories != ["/"]:
            msg = "Cannot specify both template_path and directories"
            raise SourceConfigurationError(msg)

        # Initialize templates list based on configuration
        if self.template_path:
            if not self._is_valid_template_path(self.template_path):
                raise InvalidTemplatePathError(self.VALID_EXTENSIONS)
            self.templates = [self.template_path]

    def add_templates_from_directory(self, templates: list[tuple[str, str]]) -> None:
        """Add templates found in specified directories."""
        valid_templates = []
        for path, content in templates:
            is_valid, error = self._is_valid_pipeline_template(content)
            if not is_valid:
                logging.debug("model: skipping %s: Invalid YAML - %s", path, error)
                continue

            valid_templates.append(path)
            logging.debug("model: added valid template: %s", path)

        self.templates.extend(valid_templates)

    def _is_valid_template_path(self, path: str) -> bool:
        """Check if a path is a valid template path."""
        return any(path.endswith(ext) for ext in self.VALID_EXTENSIONS)

    def _is_in_specified_directories(self, path: str) -> bool:
        """Check if path is within specified directories."""
        if self.directories == ["/"]:
            return True
        return any(path.startswith(directory.rstrip("/") + "/") for directory in self.directories)

    def _is_valid_pipeline_template(
        self,
        yaml_content: str,
    ) -> tuple[bool, str | None]:
        """
        Validates YAML content for Azure Pipeline templates.

        Azure Pipelines has two main YAML file types:
        1. Pipeline files: Complete pipeline definitions that can be run directly
        2. Template files: Reusable components that define steps, jobs, or stages

        While pipeline files must follow the strict Azure Pipeline schema:
        https://raw.githubusercontent.com/Microsoft/azure-pipelines-vscode/main/service-schema.json

        Template files are more flexible and can contain:
        - parameters: Input parameters for the template
        - variables: Shared variables
        - steps: Individual tasks/commands to run
        - jobs: Groups of steps that run on an agent
        - stages: Groups of jobs
        - extends: References to other templates

        We validate templates by checking for these common top-level keys rather than
        using the full pipeline schema, since templates:
        1. Are not meant to be run directly
        2. Can be partial pipeline definitions
        3. May contain parameter placeholder values
        4. Often use template expressions like ${{ parameters.name }}

        Args:
            yaml_content: The YAML content to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message) where:
                - is_valid: True if the YAML is a valid template
                - error_message: None if valid, otherwise describes the validation error
        """
        try:
            # Parse YAML content
            template_data = yaml.safe_load(yaml_content)
            if not template_data:
                return False, "Empty YAML content"

            # Check if it's a pipeline definition
            valid_top_level_keys = [
                "stages",
                "extends",
                "jobs",
                "steps",
                "parameters",
                "variables",
            ]
            found_keys = set(template_data.keys())

            if not any(key in found_keys for key in valid_top_level_keys):
                return False, (
                    f"Missing required pipeline keys. Found: {list(found_keys)}, "
                    f"Expected one of: {valid_top_level_keys}"
                )

            return True, None

        except yaml.YAMLError as e:
            return False, f"YAML parsing error: {e!s}"
        except Exception as e:  # noqa: BLE001
            return False, f"Validation error: {e!s}"


class TargetScope(Enum):
    """
    Defines the type of target being analyzed.
    Determines:
    - How compliance is evaluated
    - What kind of results are returned
    - How results are displayed.
    """  # noqa: D205

    ORGANIZATION = "organization"  # Analyzing entire organization
    PROJECT = "project"  # Analyzing entire project
    REPOSITORY = "repository"  # Analyzing single repository
    PIPELINE = "pipeline"  # Analyzing single pipeline

    @classmethod
    def from_string(cls, value: str) -> "TargetScope":
        """Convert a string to a TargetScope enum."""
        try:
            return cls[value.upper()]
        except KeyError as e:
            valid = ", ".join(m.name.lower() for m in cls)
            msg = f"Invalid target scope: {value}. Must be one of: {valid}"
            raise ValueError(msg) from e

    def __str__(self) -> str:
        """Return the string representation of the enum."""
        return self.name


@dataclass(frozen=True)
class AdoptionTarget:
    """
    Contains identifiers to locate the target for template adoption analysis.
    Works in conjunction with TargetScope to define what and where to analyze.

    Attributes:
        project: Name of the Azure DevOps project to check, defaults to all projects ("*") in the organization
        repository: Optional specific repository to check
        pipeline_id: Optional specific pipeline to check, if provided, repository is ignored

    Example:
        ```python
        target = AdoptionTarget(
            organization="MyORG",
            project="MyProject",
            pipeline_id=123  # Scope will be PIPELINE
        )

        target = AdoptionTarget(
            organization="MyORG",
            project="MyProject",
            repository="MyRepo"  # Scope will be REPOSITORY
        )

        target = AdoptionTarget(
            organization="MyORG",
            project="MyProject"  # Scope will be PROJECT
        )

        target = AdoptionTarget(
            organization="MyORG"  # Scope will be ORGANIZATION
        )
        ```
    """  # noqa: D205

    organization: str
    project: str | None = None
    repository: str | None = None
    pipeline_id: int | None = None

    def get_scope(self) -> "TargetScope":
        """Determine the scope based on provided identifiers."""
        if self.pipeline_id is not None:
            return TargetScope.PIPELINE
        if self.repository is not None:
            return TargetScope.REPOSITORY
        if self.project is not None:
            return TargetScope.PROJECT
        return TargetScope.ORGANIZATION


class ComplianceMode(Enum):
    """
    Defines how compliance is determined.

    ANY:
    An organization is compliant if ANY of its projects are compliant.
    A project is compliant if ANY of its repositories are compliant.
    A repository is compliant if ANY of its pipelines are compliant.

    MAJORITY:
    An organization is compliant if the majority of its projects are compliant.
    A project is compliant if the majority of its repositories are compliant.
    A repository is compliant if the majority of its pipelines are compliant.

    ALL:
    An organization is compliant if ALL of its projects are compliant.
    A project is compliant if ALL of its repositories are compliant.
    A repository is compliant if ALL of its pipelines are compliant.
    """

    ANY = auto()
    MAJORITY = auto()
    ALL = auto()

    @classmethod
    def from_string(cls, value: str) -> "ComplianceMode":
        """Convert a string to a ComplianceMode enum."""
        try:
            return cls[value.upper()]
        except KeyError as e:
            valid_modes = ", ".join(m.name.lower() for m in cls)
            msg = f"Invalid compliance mode: {value}. Must be one of: {valid_modes}"
            raise InvalidComplianceModeError(msg) from e

    def __str__(self) -> str:
        """Return the string representation of the enum."""
        return self.name


@dataclass(frozen=True)
class Template:
    """Represents a template used in a pipeline."""

    name: str | None
    path: str
    repository: str
    project: str
    content: str | None = None


class UsageType(Enum):
    """Represents the type of pipeline library usage."""

    EXTEND = "extend"
    INCLUDE = "include"

    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value


@dataclass(frozen=True)
class Adoption:
    """Represents the adoption of template(s) in a pipeline."""

    usage_type: UsageType
    templates: list[Template]


@dataclass(frozen=False)
class Pipeline:
    """
    Represents an Azure DevOps pipeline with its configuration and content.

    Attributes:
        id: Pipeline identifier
        name: Pipeline name
        folder: Pipeline folder path
        path: Path to pipeline definition
        project_id: Project identifier
        repository_id: Repository identifier
        content: Optional pipeline YAML content
        adoption: Optional adoption information
    """

    id: int
    name: str
    folder: str
    path: str | None = None
    project_id: str | None = None
    repository_id: str | None = None
    content: str | None = None
    adoption: Adoption | None = None

    FOLDER_SEPARATOR: ClassVar[str] = "\\"

    @classmethod
    def from_get_response(
        cls,
        data: dict[str, Any],
        project_id: str,
        content: str | None = None,
    ) -> "Pipeline":
        """Creates a Pipeline instance from get API response."""
        config = data.get("configuration", {})
        repository = config.get("repository", {})

        return cls(
            id=data["id"],
            name=data["name"],
            folder=data["folder"].lstrip(cls.FOLDER_SEPARATOR),
            path=config.get("path", ""),
            project_id=project_id,
            repository_id=repository.get("id"),
            content=content,
        )

    def is_compliant(self) -> bool:
        """
        Check if the current pipeline instance is compliant.

        A pipeline is compliant if it has an adoption attribute that is not None (essentially, uses at least on template from the source).
        """  # noqa: E501
        return self.adoption is not None


@dataclass(frozen=False)
class Repository:
    """
    Represents an Azure DevOps repository with its configuration.

    Attributes:
        id: Repository identifier
        name: Repository name
        default_branch: Repository default branch
        project_id: Project identifier
        total_no_pipelines: Total count of YAML pipelines in the repository
        compliant_pipelines: List of pipelines that use tracked templates
        non_compliant_pipelines: List of pipelines that do not use tracked templates
    """

    id: str
    name: str
    default_branch: str
    project_id: str | None = None

    total_no_pipelines: int = 0
    compliant_pipelines: list["Pipeline"] = field(default_factory=list)
    non_compliant_pipelines: list["Pipeline"] = field(default_factory=list)

    @classmethod
    def from_get_response(cls, data: dict[str, Any]) -> "Repository":
        """Creates a Repository instance from API response."""
        return cls(
            id=data["id"],
            name=data["name"],
            default_branch=data.get("defaultBranch", "").replace("refs/heads/", ""),
            project_id=data["project"]["id"],
        )

    def is_compliant(self, mode: ComplianceMode) -> bool:
        """
        Check if the current repository instance is compliant based on the compliance mode.

        If the compliance mode is ANY, the repository is compliant if any of its pipelines are compliant.
        If the compliance mode is MAJORITY, the repository is compliant if the majority of its pipelines are compliant (inclusive).
        If the compliance mode is ALL, the repository is compliant if all of its pipelines are compliant.
        """  # noqa: E501
        if not self.total_no_pipelines:
            return False

        no_compliant = len(self.compliant_pipelines)

        if mode == ComplianceMode.ANY:
            return no_compliant > 0
        if mode == ComplianceMode.MAJORITY:
            return no_compliant >= self.total_no_pipelines / 2  # include half
        if mode == ComplianceMode.ALL:
            return no_compliant == self.total_no_pipelines
        return False

    @property
    def pipeline_adoption_rate(self) -> float:
        """Calculate adoption rate as percentage."""
        return (len(self.compliant_pipelines) / self.total_no_pipelines) * 100 if self.total_no_pipelines > 0 else 0.0

    @property
    def pipeline_non_compliance_rate(self) -> float:
        """Calculate non-compliant rate as percentage."""
        return (
            (len(self.non_compliant_pipelines) / self.total_no_pipelines) * 100
            if self.total_no_pipelines > 0
            else 100.0
        )


@dataclass(frozen=False)
class Project:
    """
    Represents an Azure DevOps project with its configuration.

    Attributes:
        id: Project identifier
        name: Project name
        total_no_repositories: Total count of repositories in the project
        compliant_repositories: List of repositories that use tracked templates
        non_compliant_repositories: List of repositories that do not use tracked templates
        total_no_pipelines: Total count of YAML pipelines in the project
        compliant_pipelines: List of pipelines that use tracked templates
        non_compliant_pipelines: List of pipelines that do not use tracked templates
    """

    id: str
    name: str

    total_no_repositories: int = 0
    compliant_repositories: list["Repository"] = field(default_factory=list)
    non_compliant_repositories: list["Repository"] = field(default_factory=list)

    total_no_pipelines: int = 0
    compliant_pipelines: list["Pipeline"] = field(default_factory=list)
    non_compliant_pipelines: list["Pipeline"] = field(default_factory=list)

    @classmethod
    def from_get_response(cls, data: dict[str, Any]) -> "Project":
        """Creates a Project instance from API response."""
        return cls(id=data["id"], name=data["name"])

    def is_compliant(self, mode: ComplianceMode) -> bool:
        """
        Check if the current project instance is compliant based on the compliance mode.

        If the compliance mode is ANY, the project is compliant if any of its repositories are compliant.
        If the compliance mode is MAJORITY, the project is compliant if the majority of its repositories are compliant (inclusive).
        If the compliance mode is ALL, the project is compliant if all of its repositories are compliant.
        """  # noqa: E501
        if not self.total_no_repositories:
            return False

        no_compliant = len(self.compliant_repositories)

        if mode == ComplianceMode.ANY:
            return no_compliant > 0
        if mode == ComplianceMode.MAJORITY:
            return no_compliant >= self.total_no_repositories / 2  # include half
        if mode == ComplianceMode.ALL:
            return no_compliant == self.total_no_repositories
        return False

    @property
    def repository_adoption_rate(self) -> float:
        """Calculate repository adoption rate as percentage."""
        return (
            (len(self.compliant_repositories) / self.total_no_repositories) * 100
            if self.total_no_repositories > 0
            else 0.0
        )

    @property
    def repository_non_compliance_rate(self) -> float:
        """Calculate non-compliant repository rate as percentage."""
        return (
            (len(self.non_compliant_repositories) / self.total_no_repositories) * 100
            if self.total_no_repositories > 0
            else 100.0
        )

    @property
    def pipeline_adoption_rate(self) -> float:
        """Calculate pipeline adoption rate as percentage."""
        return (len(self.compliant_pipelines) / self.total_no_pipelines) * 100 if self.total_no_pipelines > 0 else 0.0

    @property
    def pipeline_non_compliance_rate(self) -> float:
        """Calculate non-compliant pipeline rate as percentage."""
        return (
            (len(self.non_compliant_pipelines) / self.total_no_pipelines) * 100
            if self.total_no_pipelines > 0
            else 100.0
        )


@dataclass(frozen=False)
class Organization:
    """
    Represents an Azure DevOps organization with its configuration.

    Attributes:
        name: Organization name
        total_no_projects: Total count of projects in the organization
        compliant_projects: List of projects that use tracked templates
        non_compliant_projects: List of projects that do not use tracked templates
        total_no_repositories: Total count of repositories in the organization
        compliant_repositories: List of repositories that use tracked templates
        non_compliant_repositories: List of repositories that do not use tracked templates
        total_no_pipelines: Total count of pipelines in the organization
        compliant_pipelines: List of pipelines that use tracked templates
        non_compliant_pipelines: List of pipelines that do not use tracked templates
    """

    name: str

    total_no_projects: int = 0
    compliant_projects: list["Project"] = field(default_factory=list)
    non_compliant_projects: list["Project"] = field(default_factory=list)

    total_no_repositories: int = 0
    compliant_repositories: list["Repository"] = field(default_factory=list)
    non_compliant_repositories: list["Repository"] = field(default_factory=list)

    total_no_pipelines: int = 0
    compliant_pipelines: list["Pipeline"] = field(default_factory=list)
    non_compliant_pipelines: list["Pipeline"] = field(default_factory=list)

    @property
    def project_adoption_rate(self) -> float:
        """Calculate project adoption rate as percentage."""
        return (len(self.compliant_projects) / self.total_no_projects) * 100 if self.total_no_projects > 0 else 0.0

    @property
    def project_non_compliance_rate(self) -> float:
        """Calculate non-compliant project rate as percentage."""
        return (
            (len(self.non_compliant_projects) / self.total_no_projects) * 100 if self.total_no_projects > 0 else 100.0
        )

    @property
    def repository_adoption_rate(self) -> float:
        """Calculate repository adoption rate as percentage."""
        return (
            (len(self.compliant_repositories) / self.total_no_repositories) * 100
            if self.total_no_repositories > 0
            else 0.0
        )

    @property
    def repository_non_compliance_rate(self) -> float:
        """Calculate non-compliant repository rate as percentage."""
        return (
            (len(self.non_compliant_repositories) / self.total_no_repositories) * 100
            if self.total_no_repositories > 0
            else 100.0
        )

    @property
    def pipeline_adoption_rate(self) -> float:
        """Calculate pipeline adoption rate as percentage."""
        return (len(self.compliant_pipelines) / self.total_no_pipelines) * 100 if self.total_no_pipelines > 0 else 0.0

    @property
    def pipeline_non_compliance_rate(self) -> float:
        """Calculate non-compliant pipeline rate as percentage."""
        return (
            (len(self.non_compliant_pipelines) / self.total_no_pipelines) * 100
            if self.total_no_pipelines > 0
            else 100.0
        )

    def is_compliant(self, mode: ComplianceMode) -> bool:
        """
        Check if the current organization instance is compliant based on the compliance mode.

        If the compliance mode is ANY, the organization is compliant if any of its projects are compliant.
        If the compliance mode is MAJORITY, the organization is compliant if the majority of its projects are compliant (inclusive).
        If the compliance mode is ALL, the organization is compliant if all of its projects are compliant.
        """  # noqa: E501
        if not self.total_no_projects:
            return False

        no_compliant = len(self.compliant_projects)

        if mode == ComplianceMode.ANY:
            return no_compliant > 0
        if mode == ComplianceMode.MAJORITY:
            return no_compliant >= self.total_no_projects / 2  # include half
        if mode == ComplianceMode.ALL:
            return no_compliant == self.total_no_projects
        return False


@dataclass(frozen=False)
class AdoptionMetrics:
    """
    Collects and tracks template adoption metrics across different scopes.

    Core Attributes:
        target: Configuration defining what to analyze (project/repo/pipeline)
        compliance_mode: Rules for determining compliance (ANY/MAJORITY/ALL)
        template_usage: Count of how many times each template is used
        processing_time: Time taken to analyze in seconds

    Template Usage Tracking:
        - Projects using each template
        - Repositories using each template
        - Pipelines using each template

    Example:
        ```python
        metrics = AdoptionMetrics(
            target=target,
            compliance_mode=ComplianceMode.ANY
        )
        metrics.add_template_usage(
            template="templates/build.yml",
            project="MyProject",
            repository="MyRepo"
        )
        ```
    """

    # Required fields first
    target: AdoptionTarget
    compliance_mode: ComplianceMode

    # Optional fields with defaults
    template_usage: dict[str, int] = field(default_factory=dict)
    processing_time: float = 0.0

    # Private tracking collections
    _template_projects: dict[str, set] = field(
        default_factory=lambda: defaultdict(set),
        repr=False,
    )
    _template_repositories: dict[str, set] = field(
        default_factory=lambda: defaultdict(set),
        repr=False,
    )
    _template_pipelines: dict[str, set] = field(
        default_factory=lambda: defaultdict(set),
        repr=False,
    )

    def add_template_usage(
        self,
        template: str,
        project: str | None = None,
        repository: str | None = None,
        pipeline: str | None = None,
    ) -> None:
        """
        Add template usage and track which projects/repositories use it.

        Args:
            template: Template identifier
            project: Optional project name using the template
            repository: Optional repository name using the template
            pipeline: Optional pipeline name using the template
        """
        self.template_usage[template] = self.template_usage.get(template, 0) + 1
        if project:
            self._template_projects[template].add(project)
        if repository:
            self._template_repositories[template].add(repository)
        if pipeline:
            self._template_pipelines[template].add(pipeline)

    def get_template_project_count(self, template: str) -> int:
        """Get number of projects using a template."""
        return len(self._template_projects.get(template, set()))

    def get_template_repository_count(self, template: str) -> int:
        """Get number of repositories using a template."""
        return len(self._template_repositories.get(template, set()))

    def get_template_pipeline_count(self, template: str) -> int:
        """Get number of pipelines using a template."""
        return len(self._template_pipelines.get(template, set()))


class ViewMode(Enum):
    """
    Defines how to display adoption results.

    Modes:
        TARGET: Results organized by project/repository/pipeline hierarchy
        SOURCE: Results organized by template usage and coverage
        OVERVIEW: Overall metrics, trends and compliance status
        NON_COMPLIANT: Results filtered to show non-compliant resources
    """

    TARGET = "target"  # View by ADO hierarchy
    SOURCE = "source"  # View by template usage
    OVERVIEW = "overview"  # View overall metrics
    NON_COMPLIANT = "non_compliant"  # View non-compliant pipelines

    @classmethod
    def from_string(cls, value: str) -> "ViewMode":
        """Convert a string to a ViewMode enum."""
        try:
            if value == "non-compliant":
                return cls.NON_COMPLIANT
            return cls[value.upper()]
        except KeyError as e:
            valid = ", ".join(m.name.lower() for m in cls)
            msg = f"Invalid view mode: {value}. Must be one of: {valid}"
            raise InvalidViewModeError(msg) from e

    def __str__(self) -> str:
        """Return the string representation of the enum."""
        return self.name
