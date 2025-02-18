import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Tuple

import yaml


class UsageType(Enum):
    """Represents the type of pipeline library usage."""

    EXTEND = "extend"
    INCLUDE = "include"


@dataclass(frozen=True)
class Template:
    """Represents a template used in a pipeline."""

    name: Optional[str]
    path: str
    repository: str
    project: str
    content: Optional[str] = None


@dataclass(frozen=True)
class Adoption:
    """Represents the adoption of template(s) in a pipeline."""

    usage_type: UsageType
    templates: List[Template]


@dataclass(frozen=False)
class Pipeline:
    """
    Represents an Azure DevOps pipeline with its configuration and content.

    Attributes:
        id: Pipeline identifier
        name: Pipeline name
        folder: Pipeline folder path
        revision: Pipeline revision number
        path: Path to pipeline definition
        repository_id: Repository identifier
        content: Optional pipeline YAML content
        adoption: Optional adoption information
    """

    id: int
    name: str
    folder: str
    revision: int
    path: Optional[str] = None
    repository_id: Optional[str] = None
    content: Optional[str] = None
    adoption: Optional[Adoption] = None

    FOLDER_SEPARATOR: ClassVar[str] = "\\"

    @classmethod
    def from_get_response(
        cls, data: Dict[str, Any], content: Optional[str] = None
    ) -> "Pipeline":
        """Creates a Pipeline instance from get API response."""
        config = data.get("configuration", {})
        repository = config.get("repository", {})

        return cls(
            id=data["id"],
            name=data["name"],
            folder=data["folder"].lstrip(cls.FOLDER_SEPARATOR),
            revision=data["revision"],
            path=config.get("path", ""),
            repository_id=repository.get("id"),
            content=content,
        )


@dataclass(frozen=False)
class Repository:
    """
    Represents an Azure DevOps repository with its configuration.

    Attributes:
        id: Repository identifier
        name: Repository name
        default_branch: Repository default branch
        is_disabled: Flag indicating if the repository is disabled
        project: Project containing the repository
        compliant_pipelines: List of pipelines that use tracked templates
        total_yaml_pipelines: Total count of YAML pipelines in the repository
    """

    id: str
    name: str
    default_branch: str
    is_disabled: bool
    project: Optional["Project"] = None
    compliant_pipelines: List["Pipeline"] = field(default_factory=list)
    total_yaml_pipelines: int = 0

    @classmethod
    def from_get_response(cls, data: Dict[str, Any]) -> "Repository":
        """Creates a Repository instance from API response."""
        return cls(
            id=data["id"],
            name=data["name"],
            default_branch=data.get("defaultBranch", "").replace("refs/heads/", ""),
            is_disabled=data["isDisabled"],
            project=Project.from_get_response(data["project"]),
        )


@dataclass(frozen=False)
class Project:
    """
    Represents an Azure DevOps project with its configuration.

    Attributes:
        id: Project identifier
        name: Project name
        repositories: List of repositories that use tracked templates
        total_no_repositories: Total count of repositories in the project
    """

    id: str
    name: str
    compliant_repositories: List["Repository"] = field(default_factory=list)
    total_no_repositories: int = 0

    @classmethod
    def from_get_response(cls, data: Dict[str, Any]) -> "Project":
        """Creates a Project instance from API response."""
        return cls(id=data["id"], name=data["name"])


@dataclass(frozen=False)
class TemplateSource:
    """
    Represents the source templates to track for adoption.
    Can be either specific templates or all templates within directories.

    Attributes:
        project: Name of the Azure DevOps project containing templates
        repository: Name of the repository containing templates
        branch: Branch containing the templates (e.g., 'main', 'master'), defaults to 'main'
        template_path: Optional specific template to track
        directories: Optional list of directories containing templates to track, defaults to ['/']
        templates: List of all templates to track
        template_schema: Schema for the template configuration
    """

    project: str
    repository: str
    branch: str = "main"
    template_path: Optional[str] = None
    directories: List[str] = field(default_factory=lambda: ["/"])
    templates: List[str] = field(default_factory=list)
    template_schema: Dict[str, Any] = field(default_factory=dict)

    VALID_EXTENSIONS = (".yml", ".yaml")

    def __post_init__(self):
        """Validates and initializes the template source configuration."""
        if self.template_path and self.directories != ["/"]:
            raise ValueError("Cannot specify both template_path and directories")

        # Initialize templates list based on configuration
        if self.template_path:
            if not self._is_valid_template_path(self.template_path):
                raise ValueError(
                    f"Template path must end with one of: {', '.join(self.VALID_EXTENSIONS)}"
                )
            self.templates = [self.template_path]

    def add_templates_from_directory(self, templates: List[Tuple[str, str]]) -> None:
        """Add templates found in specified directories."""
        logging.info(f"Processing {len(templates)} potential templates")

        valid_templates = []
        for path, content in templates:
            is_valid, error = self._is_valid_pipeline_template(content)
            if not is_valid:
                logging.debug(f"Skipping {path}: Invalid YAML - {error}")
                continue

            valid_templates.append(path)
            logging.debug(f"Added valid template: {path}")

        self.templates.extend(valid_templates)
        logging.info(f"Added {len(valid_templates)} valid templates")

    def _is_valid_template_path(self, path: str) -> bool:
        """Check if a path is a valid template path."""
        return any(path.endswith(ext) for ext in self.VALID_EXTENSIONS)

    def _is_in_specified_directories(self, path: str) -> bool:
        """Check if path is within specified directories."""
        if self.directories == ["/"]:
            return True
        return any(
            path.startswith(directory.rstrip("/") + "/")
            for directory in self.directories
        )

    def _is_valid_pipeline_template(
        self, yaml_content: str
    ) -> Tuple[bool, Optional[str]]:
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
            return False, f"YAML parsing error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"


@dataclass(frozen=True)
class AdoptionTarget:
    """
    Represents where to look for template adoption.
    Can be a project, repository, or specific pipeline.

    Attributes:
        project_name: Name of the Azure DevOps project to check
        repository_name: Optional specific repository to check
        pipeline_id: Optional specific pipeline to check, if provided, repository_name is ignored
    """

    project_name: str
    repository_name: Optional[str] = None
    pipeline_id: Optional[int] = None
