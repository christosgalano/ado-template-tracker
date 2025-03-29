# ruff: noqa: E501
"""Command-line output formatting for template tracking results.

This module provides multiple output formatters for displaying template adoption
results. It supports different view modes and output formats through a pluggable
printer architecture with consistent output handling.

Key Components:
    AdoptionPrinter: Abstract base class defining the output contract and stream handling
    AdoptionPlainPrinter: Simple text output for basic terminals
    AdoptionRichPrinter: Rich text console output with tables and styling
    AdoptionJSONPrinter: Structured JSON output with file support
    AdoptionMarkdownPrinter: GitHub-compatible Markdown output

View Modes:
    TARGET: Results organized by project/repository/pipeline hierarchy
    SOURCE: Results organized by template usage and coverage
    OVERVIEW: Overall adoption metrics and trends

Output Handling:
    - All printers support both stdout and file output
    - Consistent output stream management via context managers
    - Abstract _write method enforcing output contract
    - UTF-8 encoding for file output

Dependencies:
    - core.models: Data models for adoption results and metrics
    - rich: Terminal formatting and table generation
    - pathlib: File path handling
    - json: JSON data formatting

Example:
    python
    from ado_template_tracker.cli.printer import AdoptionRichPrinter, ViewMode
    from ado_template_tracker.core.models import Project, AdoptionMetrics

    # Initialize printer with data
    result = Project(...)  # Project with adoption data
    metrics = AdoptionMetrics(...)  # Collected metrics

    # Use context manager for automatic resource cleanup
    with AdoptionRichPrinter(result, metrics) as printer:
        # Print results in different views
        printer.print(ViewMode.TARGET)      # Show adoption by target
        printer.print(ViewMode.SOURCE)      # Show template usage
        printer.print(ViewMode.OVERVIEW)    # Show overall metrics

    # Use JSON output with file
    with AdoptionJSONPrinter(result, metrics, output_file="adoption.json") as printer:
        printer.print()


Raises:
    TypeError: When unsupported result type is provided
    ValueError: When invalid view mode is specified
    IOError: When file output operations fail
    InvalidViewModeError: When an invalid view mode is specified
"""

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TextIO

from rich.console import Console
from rich.table import Table

from ado_template_tracker.core.exceptions import InvalidViewModeError
from ado_template_tracker.core.models import (
    AdoptionMetrics,
    Organization,
    Pipeline,
    Project,
    Repository,
    TargetScope,
    Template,
    ViewMode,
)


def format_template_path(template: Template) -> str:
    """Formats a template path in the format repository/path."""
    return f"{template.repository}/{template.path}"


def format_pipeline_path(pipeline: Pipeline) -> str:
    """Formats a pipeline path in the format folder/name."""
    return f"{pipeline.folder}/{pipeline.name}".replace("\\", "/")


class AdoptionPrinter(ABC):
    """Base printer with required type hints."""

    result: Organization | Project | Repository | Pipeline
    metrics: AdoptionMetrics
    _scope: TargetScope
    _output: TextIO | None = None  # Add this to store the output stream

    def __init__(
        self,
        result: Organization | Project | Repository | Pipeline,
        metrics: AdoptionMetrics,
    ) -> None:
        """Initialize printer with result and metrics."""
        self.result = result
        self.metrics = metrics
        self._scope = self.metrics.target.get_scope()

    def print(self, view_mode: ViewMode = ViewMode.TARGET, output_file: str | None = None) -> None:
        """
        Print adoption results in specified view mode to given output file.

        Args:
            view_mode: The view mode to use for displaying results
            output_file: Path to output file, or None for stdout
        """
        self._validate_view_mode(view_mode)

        # Handle file streams and stdout differently
        if output_file:
            # For actual files, use context manager to ensure proper closing
            with self._get_output_stream(output_file) as output:
                self._output = output
                self._print_content(view_mode)
        else:
            # For stdout, don't use with statement to avoid closing it
            self._output = sys.stdout
            self._print_content(view_mode)
            # Don't close stdout

    @abstractmethod
    def _print_content(self, view_mode: ViewMode) -> None:
        """Print content based on view mode to the configured output stream."""

    def _get_output_stream(self, output_file: str | None) -> TextIO:
        """
        Get output stream for writing.

        Args:
            output_file: Path to output file, or None for stdout

        Returns:
            TextIO: File handle or sys.stdout
        """
        if output_file:
            return Path(output_file).open("w", encoding="utf-8")
        return sys.stdout

    @abstractmethod
    def _write(self, content: str | Table | dict) -> None:
        """
        Write content to configured output stream.

        Args:
            content: Content to write (string, Table, or dictionary)
        """

    def _validate_view_mode(self, view_mode: ViewMode) -> None:
        """Validate that the view mode is one of the valid ViewMode enum values."""
        valid_modes = set(ViewMode)
        if view_mode not in valid_modes:
            valid_options = ", ".join(mode.name.lower() for mode in valid_modes)
            msg = f"Invalid view mode: {view_mode}. Must be one of: {valid_options}"
            raise InvalidViewModeError(msg)


class AdoptionPlainPrinter(AdoptionPrinter):
    """Adoption result printer with plain text output."""

    def _write(self, content: str = "") -> None:
        """Write content to configured output."""
        print(content, file=self._output)

    def _print_content(self, view_mode: ViewMode) -> None:
        """Print content based on view mode to the configured output stream."""
        if view_mode == ViewMode.TARGET:
            if self._scope == TargetScope.ORGANIZATION:
                self._print_organization()
            elif self._scope == TargetScope.PROJECT:
                self._print_project()
            elif self._scope == TargetScope.REPOSITORY:
                self._print_repository()
            else:
                self._print_pipeline()
        elif view_mode == ViewMode.SOURCE:
            self._print_source()
        elif view_mode == ViewMode.OVERVIEW:
            self._print_overview()
        else:
            self._print_non_compliant()

    def _print_organization(self) -> None:  # pragma: no cover
        """Print organization adoption data as text."""
        organization = self.result

        # Organization header with compliance
        self._write(f"\n{organization.name}")
        self._write(f"Scope: {self._scope.name.title()}")
        self._write(f"Mode: {self.metrics.compliance_mode.name.title()}")
        self._write(
            f"Status: {'Compliant' if organization.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
        )

        # Project adoption
        self._write(
            f"Project Adoption Rate: {organization.project_adoption_rate:.1f}% "
            f"({len(organization.compliant_projects)}/{organization.total_no_projects})",
        )

        # Repository adoption
        self._write(
            f"Repository Adoption Rate: {organization.repository_adoption_rate:.1f}% "
            f"({len(organization.compliant_repositories)}/{organization.total_no_repositories})",
        )

        # Pipeline adoption
        self._write(
            f"Pipeline Adoption Rate: {organization.pipeline_adoption_rate:.1f}% "
            f"({len(organization.compliant_pipelines)}/{organization.total_no_pipelines})",
        )
        self._write("=" * 80)

        # Print each project
        for project in organization.compliant_projects:
            self._write(f"\nProject: {project.name}")
            self._write(
                f"Repository Adoption Rate: {project.repository_adoption_rate:.1f}% "
                f"({len(project.compliant_repositories)}/{project.total_no_repositories})",
            )
            self._write(
                f"Pipeline Adoption Rate: {project.pipeline_adoption_rate:.1f}% "
                f"({len(project.compliant_pipelines)}/{project.total_no_pipelines})",
            )

            # Print each repository in the project
            for repo in project.compliant_repositories:
                self._write(f"\n  Repository: {repo.name}")
                self._write(
                    f"  Pipeline Adoption Rate: {repo.pipeline_adoption_rate:.1f}% "
                    f"({len(repo.compliant_pipelines)}/{repo.total_no_pipelines})",
                )

                # Print each pipeline in the repository
                for pipeline in repo.compliant_pipelines:
                    if pipeline.adoption:
                        self._write(f"\n    Pipeline: {format_pipeline_path(pipeline)}")
                        for template in pipeline.adoption.get_unique_templates():
                            self._write(f"      Template: {format_template_path(template)}")
                        self._write(f"      Usage: {pipeline.adoption.usage_type.value}")

                self._write()

            self._write("-" * 80)

    def _print_project(self) -> None:  # pragma: no cover
        """Print project adoption data as text."""
        project = self.result

        # Project header with compliance
        self._write(f"\n{project.name}")
        self._write(f"Scope: {self._scope.name.title()}")
        self._write(f"Mode: {self.metrics.compliance_mode.name.title()}")
        self._write(
            f"Status: {'Compliant' if project.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
        )

        # Repository adoption
        self._write(
            f"Repository Adoption Rate: {project.repository_adoption_rate:.1f}% "
            f"({len(project.compliant_repositories)}/{project.total_no_repositories})",
        )

        # Pipeline adoption
        self._write(
            f"Pipeline Adoption Rate: {project.pipeline_adoption_rate:.1f}% "
            f"({len(project.compliant_pipelines)}/{project.total_no_pipelines})",
        )
        self._write("=" * 80)

        for repo in project.compliant_repositories:
            self._write(f"\nRepository: {repo.name}")
            self._write(
                f"Pipeline Adoption Rate: {repo.pipeline_adoption_rate:.1f}% ({len(repo.compliant_pipelines)}/{repo.total_no_pipelines})",
            )

            for pipeline in repo.compliant_pipelines:
                if pipeline.adoption:
                    self._write(f"\n  Pipeline: {format_pipeline_path(pipeline)}")
                    for template in pipeline.adoption.get_unique_templates():
                        self._write(f"    Template: {format_template_path(template)}")
                    self._write(f"    Usage: {pipeline.adoption.usage_type.value}")
            self._write()
            self._write("-" * 80)

    def _print_repository(self) -> None:  # pragma: no cover
        """Print repository adoption data as text."""
        repository = self.result
        self._write(f"\n{repository.name}")
        self._write(f"Scope: {self._scope.name.title()}")
        self._write(f"Mode: {self.metrics.compliance_mode.name.title()}")
        self._write(
            f"Status: {'Compliant' if repository.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
        )
        self._write(
            f"Pipeline Adoption Rate: {repository.pipeline_adoption_rate:.1f}% ({len(repository.compliant_pipelines)}/{repository.total_no_pipelines})",
        )
        self._write("=" * 80)

        for pipeline in repository.compliant_pipelines:
            if pipeline.adoption:
                self._write(f"\nPipeline: {format_pipeline_path(pipeline)}")
                for template in pipeline.adoption.get_unique_templates():
                    self._write(f"  Template: {format_template_path(template)}")
                self._write(f"  Usage: {pipeline.adoption.usage_type.value}")
            self._write()
            self._write("-" * 80)

    def _print_pipeline(self) -> None:  # pragma: no cover
        """Print pipeline adoption data as text."""
        pipeline = self.result
        self._write(f"\n{format_pipeline_path(pipeline)}")
        self._write(f"Scope: {self._scope.name.title()}")
        self._write(
            f"Status: {'Compliant' if pipeline.is_compliant() else 'Non-compliant'}\n",
        )
        self._write("=" * 80)

        if pipeline.adoption:
            for template in pipeline.adoption.get_unique_templates():
                usage_count = self.metrics.template_usage.get(template.path, 0)
                self._write(f"Template: {format_template_path(template)}")
                self._write(f"Usage Type: {pipeline.adoption.usage_type.value}")
                self._write(f"Usage Count: Used in {usage_count} pipeline(s)")
                self._write()
                self._write("-" * 80)

    def _print_source(self) -> None:  # pragma: no cover
        """Print template-centric view of adoption as text."""
        self._write("\nTemplate Statistics")
        self._write("=" * 80)

        total_uses = sum(self.metrics.template_usage.values())

        # Print header based on scope
        if self._scope == TargetScope.ORGANIZATION:
            self._write("\nTemplate Usage (by projects, repositories, and pipelines)")
        elif self._scope == TargetScope.PROJECT:
            self._write("\nTemplate Usage (by repositories and pipelines)")
        elif self._scope == TargetScope.REPOSITORY:
            self._write("\nTemplate Usage (by pipelines)")
        else:
            self._write("\nTemplate Usage")

        self._write("-" * 80)

        # Sort templates by usage count, highest first
        for template, count in sorted(
            self.metrics.template_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            usage_percent = f"{round(count / total_uses * 100, 2):.2f}%" if total_uses > 0 else "0.00%"
            self._write(f"\nTemplate: {template}")
            self._write(f"Usage Count: {count} ({usage_percent} of total usage)")

            # Add scope-specific counts
            if self._scope == TargetScope.ORGANIZATION:
                project_count = self.metrics.get_template_project_count(template)
                repo_count = self.metrics.get_template_repository_count(template)
                pipeline_count = self.metrics.get_template_pipeline_count(template)
                self._write(f"Projects: {project_count}")
                self._write(f"Repositories: {repo_count}")
                self._write(f"Pipelines: {pipeline_count}")
            elif self._scope == TargetScope.PROJECT:
                repo_count = self.metrics.get_template_repository_count(template)
                pipeline_count = self.metrics.get_template_pipeline_count(template)
                self._write(f"Repositories: {repo_count}")
                self._write(f"Pipelines: {pipeline_count}")
            elif self._scope == TargetScope.REPOSITORY:
                pipeline_count = self.metrics.get_template_pipeline_count(template)
                self._write(f"Pipelines: {pipeline_count}")

            self._write("-" * 60)

        # Print summary
        self._write(f"\nTotal Templates: {len(self.metrics.template_usage)}")
        self._write(f"Usage Count: {total_uses}")
        self._write(f"Processing Time: {self.metrics.processing_time:.2f}s")

    def _print_overview(self) -> None:  # pragma: no cover
        """Print overview data as text."""
        self._write("\nAdoption Overview")
        self._write("=" * 80)

        # Compliance Information
        self._write(f"\nName: {self.result.name}")
        self._write(f"Scope: {self._scope.name.title()}")
        self._write(f"Mode: {self.metrics.compliance_mode.name.title()}")

        total_compliant = 0
        if self._scope == TargetScope.PIPELINE:
            self._write(
                f"Status: {'Compliant' if self.result.is_compliant() else 'Non-Compliant'}",
            )
        else:
            self._write(
                f"Status: {'Compliant' if self.result.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
            )
            total_compliant = len(self.result.compliant_pipelines)

        # Template Statistics
        self._write("\nTemplate Statistics:")
        self._write(f"Total Templates: {len(self.metrics.template_usage)}")
        self._write(f"Usage Count: {sum(self.metrics.template_usage.values())}")

        # Most used templates
        self._write("\nMost Used Templates:")
        for template, count in sorted(
            self.metrics.template_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:3]:  # Top 3
            if total_compliant > 0:
                usage_percent = count / total_compliant * 100
                self._write(
                    f"  - {template}: {count} use(s) ({usage_percent:.1f}% of compliant pipelines)",
                )
            else:
                self._write(f"  - {template}: {count} use(s)")

        # Adoption metrics (scope-specific)
        self._write("\nAdoption Rates:")

        # Always show pipeline metrics for non-pipeline scopes
        if self._scope != TargetScope.PIPELINE:
            self._write(
                f"Pipeline Adoption Rate: {self.result.pipeline_adoption_rate:.1f}% "
                f"({len(self.result.compliant_pipelines)}/{self.result.total_no_pipelines})",
            )

        # Show repository metrics for organization and project scopes
        if self._scope not in {TargetScope.REPOSITORY, TargetScope.PIPELINE}:
            self._write(
                f"Repository Adoption Rate: {self.result.repository_adoption_rate:.1f}% "
                f"({len(self.result.compliant_repositories)}/{self.result.total_no_repositories})",
            )

        # Show project metrics for organization scope
        if self._scope == TargetScope.ORGANIZATION:
            self._write(
                f"Project Adoption Rate: {self.result.project_adoption_rate:.1f}% "
                f"({len(self.result.compliant_projects)}/{self.result.total_no_projects})",
            )

        # Performance metrics
        self._write(f"\nProcessing Time: {self.metrics.processing_time:.2f}s")

    def _print_non_compliant(self) -> None:  # pragma: no cover  # noqa: C901, PLR0912, PLR0915
        """Print non-compliant items summary as text."""
        self._write("\nNon-Compliance Report")
        self._write("=" * 80)

        # Basic compliance information
        self._write(f"\nName: {self.result.name}")
        self._write(f"Scope: {self._scope.name.title()}")
        self._write(f"Mode: {self.metrics.compliance_mode.name.title()}")

        # Check Status with appropriate method based on scope
        if self._scope == TargetScope.PIPELINE:
            is_compliant = self.result.is_compliant()
        else:
            is_compliant = self.result.is_compliant(self.metrics.compliance_mode)

        self._write(f"Status: {'Compliant' if is_compliant else 'Non-Compliant'}")
        self._write(f"Processing Time: {self.metrics.processing_time:.2f}s")
        self._write()

        # Pipeline scope - simplified output
        if self._scope == TargetScope.PIPELINE:
            pipeline = self.result
            if pipeline.is_compliant():
                if pipeline.adoption:
                    self._write(f"Templates ({pipeline.adoption.usage_type.value}):")
                    for template in pipeline.adoption.get_unique_templates():
                        self._write(f"- {format_template_path(template)}")
            else:
                self._write("This pipeline is non-compliant.")
                self._write("No template usage detected from required sources.")

        # Non-pipeline scopes
        # Show non-compliant statistics based on scope
        elif self._scope == TargetScope.ORGANIZATION:
            organization = self.result
            self._write("Non-Compliance Statistics:")
            self._write(
                f"- Non-Compliant Projects: {organization.project_non_compliance_rate:.1f}% "
                f"({len(organization.non_compliant_projects)}/{organization.total_no_projects})",
            )
            self._write(
                f"- Non-Compliant Repositories: {organization.repository_non_compliance_rate:.1f}% "
                f"({len(organization.non_compliant_repositories)}/{organization.total_no_repositories})",
            )
            self._write(
                f"- Non-Compliant Pipelines: {organization.pipeline_non_compliance_rate:.1f}% "
                f"({len(organization.non_compliant_pipelines)}/{organization.total_no_pipelines})",
            )
            if organization.non_compliant_projects:
                self._write("\nNon-Compliant Projects:")
                for project in organization.non_compliant_projects:
                    self._write(f"- {project.name}")
            if organization.non_compliant_repositories:
                self._write("\nNon-Compliant Repositories:")
                for repository in organization.non_compliant_repositories:
                    self._write(f"- {repository.name}")
            if organization.non_compliant_pipelines:
                self._write("\nNon-Compliant Pipelines:")
                for pipeline in organization.non_compliant_pipelines:
                    self._write(f"- {format_pipeline_path(pipeline)}")

        elif self._scope == TargetScope.PROJECT:
            project = self.result
            self._write("Non-Compliance Statistics:")
            self._write(
                f"- Non-Compliant Repositories: {project.repository_non_compliance_rate:.1f}% "
                f"({len(project.non_compliant_repositories)}/{project.total_no_repositories})",
            )
            self._write(
                f"- Non-Compliant Pipelines: {project.pipeline_non_compliance_rate:.1f}% "
                f"({len(project.non_compliant_pipelines)}/{project.total_no_pipelines})",
            )
            if project.non_compliant_repositories:
                self._write("\nNon-Compliant Repositories:")
                for repository in project.non_compliant_repositories:
                    self._write(f"- {repository.name}")
            if project.non_compliant_pipelines:
                self._write("\nNon-Compliant Pipelines:")
                for pipeline in project.non_compliant_pipelines:
                    self._write(f"- {format_pipeline_path(pipeline)}")

        elif self._scope == TargetScope.REPOSITORY:
            repository = self.result
            self._write("Non-Compliance Statistics:")
            self._write(
                f"- Non-Compliant Pipelines: {repository.pipeline_non_compliance_rate:.1f}% "
                f"({len(repository.non_compliant_pipelines)}/{repository.total_no_pipelines})",
            )
            if repository.non_compliant_pipelines:
                self._write("\nNon-Compliant Pipelines:")
                for pipeline in repository.non_compliant_pipelines:
                    self._write(f"- {format_pipeline_path(pipeline)}")


class AdoptionRichPrinter(AdoptionPrinter):
    """Adoption result printer with rich text formatting."""

    def _write(self, content: str | Table) -> None:
        """Write content to configured output."""
        self._console.print(content)

    def _print_content(self, view_mode: ViewMode) -> None:
        """Print content based on view mode to the configured output stream."""
        # Initialize console with the current output stream
        self._console = Console(file=self._output)

        if view_mode == ViewMode.TARGET:
            if self._scope == TargetScope.ORGANIZATION:
                self._print_organization_adoption()
            elif self._scope == TargetScope.PROJECT:
                self._print_project_adoption()
            elif self._scope == TargetScope.REPOSITORY:
                self._print_repository_adoption()
            else:
                self._print_pipeline_adoption()
        elif view_mode == ViewMode.SOURCE:
            self._print_source()
        elif view_mode == ViewMode.OVERVIEW:
            self._print_overview()
        else:
            self._print_non_compliant()

    def _print_organization_adoption(self) -> None:  # pragma: no cover
        """Print adoption report for an entire organization with metrics."""
        organization = self.result

        # Organization header with Status
        table = Table(
            title=(
                f"Organization '{organization.name}' - "
                f"[{'green' if organization.is_compliant(self.metrics.compliance_mode) else 'red'}]"
                f"{'Compliant' if organization.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}[/] "
                f"({self.metrics.compliance_mode.name} mode)\n"
                f"Pipeline Adoption: {organization.pipeline_adoption_rate:.1f}% "
                f"({len(organization.compliant_pipelines)}/{organization.total_no_pipelines})\n"
                f"Repository Adoption: {organization.repository_adoption_rate:.1f}% "
                f"({len(organization.compliant_repositories)}/{organization.total_no_repositories})\n"
                f"Project Adoption: {organization.project_adoption_rate:.1f}% "
                f"({len(organization.compliant_projects)}/{organization.total_no_projects})"
            ),
        )

        table.add_column("Project", style="purple")
        table.add_column("Repository", style="blue")
        table.add_column("Pipeline", style="cyan")
        table.add_column("Template(s)", style="green")
        table.add_column("Usage", style="magenta", justify="center")

        for project in organization.compliant_projects:
            first_repository = True
            for repo in project.compliant_repositories:
                first_pipeline = True
                for pipeline in repo.compliant_pipelines:
                    if pipeline.adoption:
                        template_paths = [format_template_path(t) for t in pipeline.adoption.get_unique_templates()]

                        table.add_row(
                            project.name if first_repository else "",
                            repo.name if first_pipeline else "",
                            format_pipeline_path(pipeline),
                            "\n".join(template_paths),
                            pipeline.adoption.usage_type.value,
                        )
                        first_pipeline = False
                first_repository = False

                if repo.compliant_pipelines:
                    table.add_row("", "", "", "", "")

            if project.compliant_repositories:
                for _ in range(2):
                    table.add_row("", "", "", "", "")

        self._write(table)
        self._print_metrics_summary()

    def _print_project_adoption(self) -> None:  # pragma: no cover
        """Print adoption report for an entire project with metrics."""
        project = self.result

        # Project header with Status
        table = Table(
            title=(
                f"Project '{project.name}' - "
                f"[{'green' if project.is_compliant(self.metrics.compliance_mode) else 'red'}]"
                f"{'Compliant' if project.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}[/] "
                f"({self.metrics.compliance_mode.name} mode)\n"
                f"Pipeline Adoption: {project.pipeline_adoption_rate:.1f}% "
                f"({len(project.compliant_pipelines)}/{project.total_no_pipelines})\n"
                f"Repository Adoption: {project.repository_adoption_rate:.1f}% "
                f"({len(project.compliant_repositories)}/{project.total_no_repositories})"
            ),
        )

        table.add_column("Repository", style="cyan")
        table.add_column("Pipeline", style="green")
        table.add_column("Template(s)", style="blue")
        table.add_column("Usage", style="magenta", justify="center")
        table.add_column("Adoption Rate", style="yellow", justify="right")

        for repo in project.compliant_repositories:
            first_pipeline = True
            for pipeline in repo.compliant_pipelines:
                if pipeline.adoption:
                    template_paths = [format_template_path(t) for t in pipeline.adoption.get_unique_templates()]

                    table.add_row(
                        repo.name if first_pipeline else "",
                        format_pipeline_path(pipeline),
                        "\n".join(template_paths),
                        pipeline.adoption.usage_type.value,
                        "",
                    )
                    first_pipeline = False

            # Repository summary with metrics
            if repo.compliant_pipelines:
                repo_adoption_rate = (
                    f"{repo.pipeline_adoption_rate:.1f}% ({len(repo.compliant_pipelines)}/{repo.total_no_pipelines})"
                )
                table.add_row(
                    "",
                    "[bold]Repository Total[/bold]",
                    "",
                    "",
                    f"[bold]{repo_adoption_rate}[/bold]",
                )
                if repo != project.compliant_repositories[-1]:
                    table.add_row("", "", "", "", "")

        self._write(table)
        self._print_metrics_summary()

    def _print_repository_adoption(self) -> None:  # pragma: no cover
        """Print adoption report for a specific repository with metrics."""
        repository = self.result
        is_compliant = repository.is_compliant(self.metrics.compliance_mode)

        table = Table(
            title=(
                f"Repository '{repository.name}' - "
                f"[{'green' if is_compliant else 'red'}]"
                f"{'Compliant' if is_compliant else 'Non-Compliant'}[/] "
                f"({self.metrics.compliance_mode.name} mode)\n"
                f"Pipeline Adoption: {repository.pipeline_adoption_rate:.1f}% "
                f"({len(repository.compliant_pipelines)}/{repository.total_no_pipelines})"
            ),
        )

        table.add_column("Pipeline", style="cyan")
        table.add_column("Template(s)", style="blue")
        table.add_column("Usage", style="magenta", justify="center")

        for pipeline in repository.compliant_pipelines:
            if pipeline.adoption:
                template_paths = [format_template_path(t) for t in pipeline.adoption.get_unique_templates()]

                table.add_row(
                    format_pipeline_path(pipeline),
                    "\n".join(template_paths),
                    pipeline.adoption.usage_type.value,
                )

        self._write(table)
        self._print_metrics_summary()

    def _print_pipeline_adoption(self) -> None:  # pragma: no cover
        """Print adoption report for a specific pipeline with metrics."""
        pipeline = self.result

        table = Table(
            title=(
                f"Pipeline '{pipeline.name}' - "
                f"[{'green' if pipeline.is_compliant() else 'red'}]"
                f"{'Compliant' if pipeline.is_compliant() else 'Non-Compliant'}[/] "
                f"({self.metrics.compliance_mode.name} mode)"
            ),
        )

        table.add_column("Template", style="cyan")
        table.add_column("Usage", style="magenta", justify="center")
        table.add_column("Template Usage", style="yellow", justify="right")

        if pipeline.adoption:
            for template in pipeline.adoption.get_unique_templates():
                usage_count = self.metrics.template_usage.get(template.path, 0)
                table.add_row(
                    template.path,
                    pipeline.adoption.usage_type.value,
                    f"Used in {usage_count} pipeline(s)",
                )

        self._write(table)
        self._print_metrics_summary()

    def _print_metrics_summary(self) -> None:  # pragma: no cover
        """Print a concise metrics summary."""
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")

        if self.metrics.template_usage:
            top_templates = sorted(
                self.metrics.template_usage.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            summary_table.add_row(
                "Most Used Templates:",
                ", ".join(f"{t} ({c} use(s))" for t, c in top_templates),
            )

        summary_table.add_row("Processing Time:", f"{self.metrics.processing_time:.2f}s")

        self._write("\n[bold]Additional Metrics[/bold]")
        self._write(summary_table)

    def _print_source(self) -> None:  # pragma: no cover
        """Print template-centric view of adoption."""
        table = Table(title="Template Statistics")

        # Always add these columns
        table.add_column("Template", style="cyan")
        table.add_column("Usage Count", style="green", justify="right")
        table.add_column("Usage %", style="yellow", justify="right")

        # Add scope-specific columns
        if self._scope == TargetScope.ORGANIZATION:
            table.add_column("Projects", style="magenta", justify="right")
            table.add_column("Repositories", style="blue", justify="right")
            table.add_column("Pipelines", style="purple", justify="right")
        elif self._scope == TargetScope.PROJECT:
            table.add_column("Repositories", style="blue", justify="right")
            table.add_column("Pipelines", style="purple", justify="right")
        elif self._scope == TargetScope.REPOSITORY:
            table.add_column("Pipelines", style="purple", justify="right")

        total_uses = sum(self.metrics.template_usage.values())

        for template, count in sorted(
            self.metrics.template_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            usage_percent = f"{count / total_uses * 100:.1f}%" if total_uses > 0 else "0.0%"

            # Create row with basic info
            row = [template, str(count), usage_percent]

            # Add scope-specific counts
            if self._scope == TargetScope.ORGANIZATION:
                project_count = self.metrics.get_template_project_count(template)
                repo_count = self.metrics.get_template_repository_count(template)
                pipeline_count = self.metrics.get_template_pipeline_count(template)
                row.extend([str(project_count), str(repo_count), str(pipeline_count)])
            elif self._scope == TargetScope.PROJECT:
                repo_count = self.metrics.get_template_repository_count(template)
                pipeline_count = self.metrics.get_template_pipeline_count(template)
                row.extend([str(repo_count), str(pipeline_count)])
            elif self._scope == TargetScope.REPOSITORY:
                pipeline_count = self.metrics.get_template_pipeline_count(template)
                row.append(str(pipeline_count))

            table.add_row(*row)

        self._write(table)
        self._print_metrics_summary()

    def _print_overview(self) -> None:  # pragma: no cover
        """Print overall overview and trends based on scope."""
        table = Table(title=f"Adoption Overview for {self.result.name}")

        # Add columns
        table.add_column("Category", style="cyan")
        table.add_column("Metric", style="blue")
        table.add_column("Value", style="green")
        table.add_column("Details", style="yellow")

        # Status Section
        table.add_row(
            "[bold]Compliance Information[/bold]",
            "Mode",
            self.metrics.compliance_mode.name,
            f"Scope: {self._scope.name}",
        )

        if self._scope == TargetScope.PIPELINE:
            is_compliant = self.result.is_compliant()
        else:
            is_compliant = self.result.is_compliant(self.metrics.compliance_mode)

        table.add_row(
            "",
            "Status",
            "[green]Compliant[/green]" if is_compliant else "[red]Non-Compliant[/red]",
            f"Based on {self.metrics.compliance_mode.name} mode",
        )

        table.add_section()

        # Template Usage Section
        template_header = "[bold]Template Statistics[/bold]"

        table.add_row(
            template_header,
            "Total Templates",
            str(len(self.metrics.template_usage)),
            f"{sum(self.metrics.template_usage.values())} total use(s)",
        )

        # Most used templates (top 3)
        top_templates = sorted(
            self.metrics.template_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:3]

        for template, count in top_templates:
            # Handle pipeline scope differently since it doesn't have compliant_pipelines
            if self._scope == TargetScope.PIPELINE:
                # For pipeline scope, just show count without percentage
                table.add_row("", template, f"{count} use(s)", "Single pipeline view")
            else:
                # For other scopes, calculate percentage of compliant pipelines
                usage_percent = (
                    round(
                        count / len(self.result.compliant_pipelines) * 100,
                        1,
                    )
                    if len(self.result.compliant_pipelines) > 0
                    else 0
                )
                table.add_row(
                    "",
                    template,
                    f"{count} use(s)",
                    f"{usage_percent:.1f}% of compliant pipelines",
                )

        # Adoption metrics based on scope
        if self._scope != TargetScope.PIPELINE:
            table.add_section()
            table.add_row(
                "[bold]Adoption Rates[/bold]",
                "Pipeline Adoption",
                f"{self.result.pipeline_adoption_rate:.1f}%",
                f"{len(self.result.compliant_pipelines)} of {self.result.total_no_pipelines} pipelines",
            )

            if self._scope != TargetScope.REPOSITORY:
                table.add_row(
                    "",
                    "Repository Adoption",
                    f"{self.result.repository_adoption_rate:.1f}%",
                    f"{len(self.result.compliant_repositories)} of {self.result.total_no_repositories} repositories",
                )

            if self._scope == TargetScope.ORGANIZATION:
                table.add_row(
                    "",
                    "Project Adoption",
                    f"{self.result.project_adoption_rate:.1f}%",
                    f"{len(self.result.compliant_projects)} of {self.result.total_no_projects} projects",
                )

        # Performance Section
        table.add_section()
        table.add_row(
            "[bold]Performance[/bold]",
            "Processing Time",
            f"{self.metrics.processing_time:.2f}s",
            "",
        )

        self._write(table)

    def _print_non_compliant(self) -> None:  # pragma: no cover  # noqa: C901, PLR0912, PLR0915
        """Print non-compliant items summary with rich text formatting."""
        # Create header table with basic information
        info_table = Table(
            title="Non-Compliance Report",
            show_header=False,
            box=None,
        )
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="yellow")

        # Check Status with appropriate method based on scope
        if self._scope == TargetScope.PIPELINE:
            is_compliant = self.result.is_compliant()
        else:
            is_compliant = self.result.is_compliant(self.metrics.compliance_mode)
        compliance_status = "[green]Compliant[/green]" if is_compliant else "[red]Non-Compliant[/red]"

        info_table.add_row("Scope", self._scope.name)
        info_table.add_row("Name", self.result.name)
        info_table.add_row("Mode", self.metrics.compliance_mode.name)
        info_table.add_row("Status", compliance_status)
        info_table.add_row("Processing Time", f"{self.metrics.processing_time:.2f}s")
        info_table.add_row("", "")
        self._write(info_table)

        if self._scope == TargetScope.PIPELINE:
            pipeline = self.result
            if pipeline.is_compliant():
                status_table = Table(title="Compliance Details")
                status_table.add_column("Templates", style="yellow")
                status_table.add_column("Usage Type", style="yellow")
                templates = []
                if pipeline.adoption:
                    for template in pipeline.adoption.get_unique_templates():
                        templates.extend([format_template_path(template)])
                status_table.add_row("\n".join(templates), pipeline.adoption.usage_type.value)
                self._write(status_table)
        else:
            # Create statistics table for all non-pipeline scopes
            stats_table = Table(title="Non-Compliance Statistics")
            stats_table.add_column("Resource Type", style="blue")
            stats_table.add_column("Non-Compliant", style="red", justify="right")
            stats_table.add_column("Total", justify="right")
            stats_table.add_column("Percentage", style="magenta", justify="right")

            if self._scope == TargetScope.ORGANIZATION:
                organization = self.result
                stats_table.add_row(
                    "Projects",
                    str(len(organization.non_compliant_projects)),
                    str(organization.total_no_projects),
                    f"{organization.project_non_compliance_rate:.1f}%",
                )
                stats_table.add_row(
                    "Repositories",
                    str(len(organization.non_compliant_repositories)),
                    str(organization.total_no_repositories),
                    f"{organization.repository_non_compliance_rate:.1f}%",
                )
                stats_table.add_row(
                    "Pipelines",
                    str(len(organization.non_compliant_pipelines)),
                    str(organization.total_no_pipelines),
                    f"{organization.pipeline_non_compliance_rate:.1f}%",
                )
                self._write(stats_table)

                if organization.non_compliant_projects:
                    projects_table = Table(title="Non-Compliant Projects")
                    projects_table.add_column("Project", style="red")
                    for project in organization.non_compliant_projects:
                        projects_table.add_row(project.name)
                    self._write(projects_table)

                if organization.non_compliant_repositories:
                    repos_table = Table(title="Non-Compliant Repositories")
                    repos_table.add_column("Repository", style="red")
                    for repository in organization.non_compliant_repositories:
                        repos_table.add_row(repository.name)
                    self._write(repos_table)

                if organization.non_compliant_projects:
                    pipelines_table = Table(title="Non-Compliant Pipelines")
                    pipelines_table.add_column("Pipeline", style="red")
                    for pipeline in organization.non_compliant_pipelines:
                        pipelines_table.add_row(format_pipeline_path(pipeline))
                    self._write(pipelines_table)

            elif self._scope == TargetScope.PROJECT:
                project = self.result
                stats_table.add_row(
                    "Repositories",
                    str(len(project.non_compliant_repositories)),
                    str(project.total_no_repositories),
                    f"{project.repository_non_compliance_rate:.1f}%",
                )
                stats_table.add_row(
                    "Pipelines",
                    str(len(project.non_compliant_pipelines)),
                    str(project.total_no_pipelines),
                    f"{project.pipeline_non_compliance_rate:.1f}%",
                )
                self._write(stats_table)

                if project.non_compliant_repositories:
                    repos_table = Table(title="Non-Compliant Repositories")
                    repos_table.add_column("Repository", style="red")
                    for repository in project.non_compliant_repositories:
                        repos_table.add_row(repository.name)
                    self._write(repos_table)

                if project.non_compliant_pipelines:
                    pipelines_table = Table(title="Non-Compliant Pipelines")
                    pipelines_table.add_column("Pipeline", style="red")
                    for pipeline in project.non_compliant_pipelines:
                        pipelines_table.add_row(format_pipeline_path(pipeline))
                    self._write(pipelines_table)

            elif self._scope == TargetScope.REPOSITORY:
                repository = self.result
                stats_table.add_row(
                    "Pipelines",
                    str(len(repository.non_compliant_pipelines)),
                    str(repository.total_no_pipelines),
                    f"{repository.pipeline_non_compliance_rate:.1f}%",
                )
                self._write(stats_table)

                if repository.non_compliant_pipelines:
                    details_table = Table(title="Non-Compliant Pipelines", show_header=False)
                    details_table.add_column("Pipeline", style="red")
                    for pipeline in repository.non_compliant_pipelines:
                        details_table.add_row(f"- {format_pipeline_path(pipeline)}")
                    self._write(details_table)


class AdoptionJSONPrinter(AdoptionPrinter):
    """Adoption result printer with JSON output."""

    def _write(self, content: dict) -> None:
        """Write JSON content to configured output."""
        json.dump(content, self._output, indent=2)
        self._output.write("\n")

    def _print_content(self, view_mode: ViewMode) -> None:
        """Print content based on view mode to the configured output stream."""
        if view_mode in {ViewMode.TARGET, ViewMode.NON_COMPLIANT}:
            if self._scope == TargetScope.ORGANIZATION:
                data = self._get_organization(self.result, view_mode)
            elif self._scope == TargetScope.PROJECT:
                data = self._get_project(self.result, view_mode)
            elif self._scope == TargetScope.REPOSITORY:
                data = self._get_repository(self.result, view_mode)
            else:
                data = self._get_pipeline(self.result, view_mode)
        elif view_mode == ViewMode.SOURCE:
            data = self._get_source()
        elif view_mode == ViewMode.OVERVIEW:
            data = self._get_overview()
        self._write(data)

    def _get_organization(self, organization: Organization, view_mode: ViewMode) -> dict:  # pragma: no cover
        """Print organization adoption data as dict."""
        data = {
            "name": organization.name,
            "compliance_mode": str(self.metrics.compliance_mode),
            "is_compliant": organization.is_compliant(self.metrics.compliance_mode),
        }
        if view_mode != ViewMode.NON_COMPLIANT:
            projects = []
            for p in organization.compliant_projects:
                project_data = self._get_project(p, view_mode)
                project_data.pop("compliance_mode")
                project_data.pop("is_compliant")
                projects.append(project_data)
            data.update(
                {
                    "project_adoption": {
                        "adoption_rate": round(organization.project_adoption_rate, 2),
                        "compliant_projects": len(organization.compliant_projects),
                        "total_projects": organization.total_no_projects,
                    },
                    "repository_adoption": {
                        "adoption_rate": round(organization.repository_adoption_rate, 2),
                        "compliant_repositories": len(organization.compliant_repositories),
                        "total_repositories": organization.total_no_repositories,
                    },
                    "pipeline_adoption": {
                        "adoption_rate": round(organization.pipeline_adoption_rate, 2),
                        "compliant_pipelines": len(organization.compliant_pipelines),
                        "total_pipelines": organization.total_no_pipelines,
                    },
                    "compliant_projects": projects,
                },
            )
        else:
            projects = []
            for p in organization.non_compliant_projects:
                project_data = self._get_project(p, view_mode)
                project_data.pop("compliance_mode")
                project_data.pop("is_compliant")
                projects.append(project_data)
            data.update(
                {
                    "project_non_compliance": {
                        "non_compliance_rate": round(organization.project_non_compliance_rate, 2),
                        "non_compliant_projects": len(organization.non_compliant_projects),
                        "total_projects": organization.total_no_projects,
                    },
                    "repository_non_compliance": {
                        "non_compliance_rate": round(organization.repository_non_compliance_rate, 2),
                        "non_compliant_repositories": len(organization.non_compliant_repositories),
                        "total_repositories": organization.total_no_repositories,
                    },
                    "pipeline_non_compliance": {
                        "non_compliance_rate": round(organization.pipeline_non_compliance_rate, 2),
                        "non_compliant_pipelines": len(organization.non_compliant_pipelines),
                        "total_pipelines": organization.total_no_pipelines,
                    },
                    "non_compliant_projects": projects,
                },
            )

        return data

    def _get_project(self, project: Project, view_mode: ViewMode) -> dict:  # pragma: no cover
        """Print project adoption data as dict."""
        data = {
            "name": project.name,
            "compliance_mode": str(self.metrics.compliance_mode),
            "is_compliant": project.is_compliant(self.metrics.compliance_mode),
        }
        if view_mode != ViewMode.NON_COMPLIANT:
            # Process compliant repositories
            repositories = []
            for r in project.compliant_repositories:
                repository_data = self._get_repository(r, view_mode)
                repository_data.pop("compliance_mode")
                repository_data.pop("is_compliant")
                repositories.append(repository_data)
            data.update(
                {
                    "repository_adoption": {
                        "adoption_rate": round(project.repository_adoption_rate, 2),
                        "compliant_repositories": len(project.compliant_repositories),
                        "total_repositories": project.total_no_repositories,
                    },
                    "pipeline_adoption": {
                        "adoption_rate": round(project.pipeline_adoption_rate, 2),
                        "compliant_pipelines": len(project.compliant_pipelines),
                        "total_pipelines": project.total_no_pipelines,
                    },
                    "compliant_repositories": repositories,
                },
            )
        else:
            # Process non-compliant repositories
            repositories = []
            for r in project.non_compliant_repositories:
                repository_data = self._get_repository(r, view_mode)
                repository_data.pop("compliance_mode")
                repository_data.pop("is_compliant")
                repositories.append(repository_data)
            data.update(
                {
                    "repository_non_compliance": {
                        "non_compliance_rate": round(project.repository_non_compliance_rate, 2),
                        "non_compliant_repositories": len(project.non_compliant_repositories),
                        "total_repositories": project.total_no_repositories,
                    },
                    "pipeline_non_compliance": {
                        "non_compliance_rate": round(project.pipeline_non_compliance_rate, 2),
                        "non_compliant_pipelines": len(project.non_compliant_pipelines),
                        "total_pipelines": project.total_no_pipelines,
                    },
                    "non_compliant_repositories": repositories,
                },
            )

        return data

    def _get_repository(
        self,
        repository: Repository,
        view_mode: ViewMode,
    ) -> dict:  # pragma: no cover
        """Get repository adoption data as dict."""
        data = {
            "name": repository.name,
            "compliance_mode": str(self.metrics.compliance_mode),
            "is_compliant": repository.is_compliant(self.metrics.compliance_mode),
        }
        if view_mode != ViewMode.NON_COMPLIANT:
            # Process compliant pipelines
            pipelines = []
            for p in repository.compliant_pipelines:
                pipeline_data = self._get_pipeline(p, view_mode)
                pipeline_data.pop("is_compliant")
                pipelines.append(pipeline_data)
            data.update(
                {
                    "adoption": {
                        "adoption_rate": round(repository.pipeline_adoption_rate, 2),
                        "compliant_pipelines": len(repository.compliant_pipelines),
                        "total_pipelines": repository.total_no_pipelines,
                    },
                    "compliant_pipelines": pipelines,
                },
            )
        else:
            # Process non-compliant pipelines
            pipelines = []
            for p in repository.non_compliant_pipelines:
                pipeline_data = self._get_pipeline(p, view_mode)
                pipeline_data.pop("is_compliant")
                pipelines.append(pipeline_data)
            data.update(
                {
                    "non_compliance": {
                        "non_compliance_rate": round(repository.pipeline_non_compliance_rate, 2),
                        "non_compliant_pipelines": len(repository.non_compliant_pipelines),
                        "total_pipelines": repository.total_no_pipelines,
                    },
                    "non_compliant_pipelines": pipelines,
                },
            )

        return data

    def _get_pipeline(self, pipeline: Pipeline, view_mode: ViewMode) -> dict:  # pragma: no cover
        """Get pipeline adoption data as dict."""
        data = {
            "name": pipeline.name,
            "is_compliant": pipeline.is_compliant(),
            "path": format_pipeline_path(pipeline),
        }
        if view_mode != ViewMode.NON_COMPLIANT:
            data.update(
                {
                    "templates": [
                        {
                            "path": format_template_path(t),
                            "usage_type": pipeline.adoption.usage_type.value,
                        }
                        for t in pipeline.adoption.get_unique_templates()
                    ]
                    if pipeline.adoption
                    else [],
                },
            )
        return data

    def _get_source(self) -> dict:  # pragma: no cover
        """
        Get template usage data as dict with scope-appropriate counts.

        Returns different coverage metrics based on scope:
        - ORGANIZATION: project, repository, and pipeline counts
        - PROJECT: repository and pipeline counts
        - REPOSITORY: pipeline count only
        """
        total_uses = sum(self.metrics.template_usage.values())
        template_data = []

        for template, count in sorted(
            self.metrics.template_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            template_info = {
                "template": template,
                "usage_count": count,
                "usage_percent": round(count / total_uses * 100, 2),
            }

            # Add appropriate counts based on scope
            if self._scope == TargetScope.ORGANIZATION:
                template_info.update(
                    {
                        "project_count": self.metrics.get_template_project_count(template),
                        "repository_count": self.metrics.get_template_repository_count(template),
                        "pipeline_count": self.metrics.get_template_pipeline_count(template),
                    },
                )
            elif self._scope == TargetScope.PROJECT:
                template_info.update(
                    {
                        "repository_count": self.metrics.get_template_repository_count(template),
                        "pipeline_count": self.metrics.get_template_pipeline_count(template),
                    },
                )
            elif self._scope == TargetScope.REPOSITORY:
                template_info["pipeline_count"] = self.metrics.get_template_pipeline_count(template)

            template_data.append(template_info)

        return template_data

    def _get_overview(self) -> dict:  # pragma: no cover
        """
        Get hierarchical overview data as dict based on scope.

        Returns different metrics based on scope:
        - ORGANIZATION: project, repository, and pipeline metrics
        - PROJECT: repository and pipeline metrics
        - REPOSITORY: pipeline metrics only
        - PIPELINE: template usage metrics only
        """
        data = {
            "name": self.result.name,
        }
        if self._scope == TargetScope.PIPELINE:
            data.update(
                {
                    "compliance": {
                        "mode": str(self.metrics.compliance_mode),
                        "scope": self._scope.name,
                        "status": "Compliant" if self.result.is_compliant() else "Non-Compliant",
                    },
                    "template_statistics": {
                        "total_templates": len(self.metrics.template_usage),
                        "total_uses": sum(self.metrics.template_usage.values()),
                        "most_used": [
                            {
                                "template": t,
                                "usage_count": c,
                            }
                            for t, c in sorted(
                                self.metrics.template_usage.items(),
                                key=lambda x: x[1],
                                reverse=True,
                            )[:3]
                        ],
                    },
                },
            )
        else:
            data.update(
                {
                    "compliance": {
                        "mode": str(self.metrics.compliance_mode),
                        "scope": self._scope.name,
                        "status": "Compliant"
                        if self.result.is_compliant(self.metrics.compliance_mode)
                        else "Non-Compliant",
                    },
                    "template_statistics": {
                        "total_templates": len(self.metrics.template_usage),
                        "total_uses": sum(self.metrics.template_usage.values()),
                        "most_used": [
                            {
                                "template": t,
                                "usage_count": c,
                                "usage_percent": round(
                                    c / len(self.result.compliant_pipelines) * 100,
                                    2,
                                )
                                if len(self.result.compliant_pipelines) > 0
                                else 0,
                            }
                            for t, c in sorted(
                                self.metrics.template_usage.items(),
                                key=lambda x: x[1],
                                reverse=True,
                            )[:3]
                        ],
                    },
                },
            )

        # Add metrics based on scope
        if self._scope == TargetScope.PIPELINE:
            return data
        data.update(
            {
                "pipeline_adoption": {
                    "adoption_rate": round(self.result.pipeline_adoption_rate, 2),
                    "compliant_pipelines": len(self.result.compliant_pipelines),
                    "total_pipelines": self.result.total_no_pipelines,
                },
            },
        )
        if self._scope in {TargetScope.PROJECT, TargetScope.ORGANIZATION}:
            data.update(
                {
                    "repository_adoption": {
                        "adoption_rate": round(self.result.repository_adoption_rate, 2),
                        "compliant_repositories": len(self.result.compliant_repositories),
                        "total_repositories": self.result.total_no_repositories,
                    },
                },
            )
        if self._scope == TargetScope.ORGANIZATION:
            data.update(
                {
                    "project_adoption": {
                        "adoption_rate": self.result.project_adoption_rate,
                        "compliant_projects": len(self.result.compliant_projects),
                        "total_projects": self.result.total_no_projects,
                    },
                },
            )
        data.update(
            {
                "performance": {
                    "processing_time": round(self.metrics.processing_time, 2),
                },
            },
        )

        return data


class AdoptionMarkdownPrinter(AdoptionPrinter):
    """Adoption result printer with Markdown output."""

    def _write(self, content: str) -> None:
        """Write Markdown content to configured output."""
        self._output.write(content)
        self._output.write("\n")

    def _print_content(self, view_mode: ViewMode) -> None:
        """Print content based on view mode to the configured output stream."""
        if view_mode == ViewMode.TARGET:
            if self._scope == TargetScope.ORGANIZATION:
                self._print_organization(self.result)
            elif self._scope == TargetScope.PROJECT:
                self._print_project(self.result)
            elif self._scope == TargetScope.REPOSITORY:
                self._print_repository(self.result)
            else:
                self._print_pipeline(self.result)
        elif view_mode == ViewMode.SOURCE:
            self._print_source()
        elif view_mode == ViewMode.OVERVIEW:
            self._print_overview()
        else:
            self._print_non_compliant()
        self._write("")

    def _print_organization(self, organization: Organization) -> None:  # pragma: no cover
        """Print organization adoption data as Markdown."""
        lines = [
            f"# {organization.name}",
            "",
            "## Adoption Summary",
            "",
            f"- Scope: {self._scope.name.title()}",
            f"- Mode: {self.metrics.compliance_mode.name.title()}",
            f"- Status: {'Compliant' if organization.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
            f"- Project Adoption Rate: {organization.project_adoption_rate:.1f}% ({len(organization.compliant_projects)}/{organization.total_no_projects})",
            f"- Repository Adoption Rate: {organization.repository_adoption_rate:.1f}% ({len(organization.compliant_repositories)}/{organization.total_no_repositories})",
            f"- Pipeline Adoption Rate: {organization.pipeline_adoption_rate:.1f}% ({len(organization.compliant_pipelines)}/{organization.total_no_pipelines})",
            "",
            "---",
            "",
            "## Project Overview",
            "",
            "| Project | Repository Adoption Rate | Pipeline Adoption Rate |",
            "|---------|------------------------|---------------------|",
        ]

        # Project overview section
        for project in organization.compliant_projects:
            project_anchor = project.name.lower().replace(" ", "-").replace("/", "-")
            repo_rate = f"{project.repository_adoption_rate:.1f}% ({len(project.compliant_repositories)}/{project.total_no_repositories})"
            pipeline_rate = f"{project.pipeline_adoption_rate:.1f}% ({len(project.compliant_pipelines)}/{project.total_no_pipelines})"
            lines.append(f"| [{project.name}](#{project_anchor}) | {repo_rate} | {pipeline_rate} |")

        # Project details section
        lines.extend(["", "---", "", "## Project Details", ""])
        for project in organization.compliant_projects:
            # Repository overview section
            lines.extend(
                [
                    f"### {project.name}",
                    "",
                    "#### Repository Overview",
                    "",
                    "| Repository | Pipeline Adoption Rate |",
                    "|------------|-----------------|",
                ],
            )
            for repo in project.compliant_repositories:
                repo_compliance = (
                    f"{repo.pipeline_adoption_rate:.1f}% ({len(repo.compliant_pipelines)}/{repo.total_no_pipelines})"
                )
                # Create anchor link - replace spaces and special chars with hyphens
                anchor = repo.name.lower().replace(" ", "-").replace("/", "-")
                lines.append(f"| [{repo.name}](#{anchor}) | {repo_compliance} |")

            # Repository details section
            lines.extend(
                [
                    "",
                    "#### Repository Details",
                    "",
                ],
            )
            for repo in project.compliant_repositories:
                lines.extend(
                    [
                        f"##### {repo.name}",
                        "",
                        "| Pipeline | Templates | Usage |",
                        "|----------|-----------|--------|",
                    ],
                )
                for pipeline in repo.compliant_pipelines:
                    if pipeline.adoption:
                        templates = "<br>".join(
                            f"`{format_template_path(t)}`" for t in pipeline.adoption.get_unique_templates()
                        )
                        lines.append(
                            f"| `{format_pipeline_path(pipeline)}` | {templates} | {pipeline.adoption.usage_type.value} |",
                        )
                lines.append("")
            lines.append("---")
            lines.append("")

        self._write("\n".join(lines))

    def _print_project(  # pragma: no cover
        self,
        project: Project,
    ) -> None:
        """Print project adoption data as Markdown."""
        lines = [
            f"# {project.name}",
            "",
            "## Adoption Summary",
            "",
            f"- Scope: {self._scope.name.title()}",
            f"- Mode: {self.metrics.compliance_mode.name.title()}",
            f"- Status: {'Compliant' if project.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
            f"- Repository Adoption Rate: {project.repository_adoption_rate:.1f}% ({len(project.compliant_repositories)}/{project.total_no_repositories})",
            f"- Pipeline Adoption Rate: {project.pipeline_adoption_rate:.1f}% ({len(project.compliant_pipelines)}/{project.total_no_pipelines})",
            "",
            "---",
            "",
            "## Repository Overview",
            "",
            "| Repository | Pipeline Adoption Rate |",
            "|------------|-----------------|",
        ]

        # Repository overview section
        for repo in project.compliant_repositories:
            repo_compliance = (
                f"{repo.pipeline_adoption_rate:.1f}% ({len(repo.compliant_pipelines)}/{repo.total_no_pipelines})"
            )
            # Create anchor link - replace spaces and special chars with hyphens
            anchor = repo.name.lower().replace(" ", "-").replace("/", "-")
            lines.append(f"| [{repo.name}](#{anchor}) | {repo_compliance} |")

        # Repository details sections
        lines.extend(["", "---", "", "## Repository Details", ""])
        for repo in project.compliant_repositories:
            lines.extend(
                [
                    f"### {repo.name}",
                    "",
                    "| Pipeline | Templates | Usage |",
                    "|----------|-----------|--------|",
                ],
            )
            for pipeline in repo.compliant_pipelines:
                if pipeline.adoption:
                    templates = "<br>".join(
                        f"`{format_template_path(t)}`" for t in pipeline.adoption.get_unique_templates()
                    )
                    lines.append(
                        f"| `{format_pipeline_path(pipeline)}` | {templates} | {pipeline.adoption.usage_type.value} |",
                    )
            lines.append("")

        self._write("\n".join(lines))

    def _print_repository(self, repository: Repository) -> None:  # pragma: no cover
        """Print repository adoption data as Markdown."""
        lines = [
            f"# {repository.name}",
            "",
            "## Adoption Summary",
            "",
            f"- Scope: {self._scope.name.title()}",
            f"- Mode: {self.metrics.compliance_mode.name.title()}",
            f"- Status: {'Compliant' if repository.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
            f"- Pipeline Adoption Rate: {repository.pipeline_adoption_rate:.1f}% ({len(repository.compliant_pipelines)}/{repository.total_no_pipelines})",
            "",
            "## Pipeline Overview",
            "",
            "| Pipeline | Templates | Usage |",
            "|----------|-----------|--------|",
        ]
        for pipeline in repository.compliant_pipelines:
            if pipeline.adoption:
                templates = "<br>".join(
                    f"`{format_template_path(t)}`" for t in pipeline.adoption.get_unique_templates()
                )
                lines.append(
                    f"| `{format_pipeline_path(pipeline)}` | {templates} | {pipeline.adoption.usage_type.value} |",
                )
        self._write("\n".join(lines))

    def _print_pipeline(self, pipeline: Pipeline) -> None:  # pragma: no cover
        """Print pipeline adoption data as Markdown."""
        lines = [
            f"# {format_pipeline_path(pipeline)}",
            "",
            "## Adoption Summary",
            "",
            f"- Scope: {self._scope.name.title()}",
            f"- Status: {'Compliant' if pipeline.is_compliant() else 'Non-compliant'}",
            "",
        ]
        if pipeline.adoption:
            lines.extend(
                [
                    "## Template Usage",
                    "",
                    "| Template | Usage Type | Usage Count |",
                    "|----------|------------|-------------|",
                ],
            )
            for template in pipeline.adoption.get_unique_templates():
                usage_count = self.metrics.template_usage.get(template.path, 0)
                lines.append(
                    f"| `{format_template_path(template)}` | {pipeline.adoption.usage_type.value} | {usage_count} |",
                )
        self._write("\n".join(lines))

    def _print_source(self) -> None:  # pragma: no cover
        """Print template usage data as Markdown."""
        total_uses = sum(self.metrics.template_usage.values())

        # Start with basic columns
        lines = [
            "# Template Statistics",
            "",
        ]

        # Prepare header rows based on scope
        if self._scope == TargetScope.ORGANIZATION:
            lines.extend(
                [
                    "| Template | Usage Count | Usage % | Projects | Repositories | Pipelines |",
                    "|----------|-------------|---------|----------|--------------|-----------|",
                ],
            )
        elif self._scope == TargetScope.PROJECT:
            lines.extend(
                [
                    "| Template | Usage Count | Usage % | Repositories | Pipelines |",
                    "|----------|-------------|---------|-------------|-----------|",
                ],
            )
        elif self._scope == TargetScope.REPOSITORY:
            lines.extend(
                [
                    "| Template | Usage Count | Usage % | Pipelines |",
                    "|----------|-------------|---------|-----------|",
                ],
            )
        else:
            lines.extend(
                [
                    "| Template | Usage Count | Usage % |",
                    "|----------|-------------|---------|",
                ],
            )

        # Generate table rows
        for template, count in sorted(
            self.metrics.template_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            usage_percent = f"{round(count / total_uses * 100, 2):.2f}%"

            row = f"| `{template}` | {count} | {usage_percent}"

            # Add counts based on scope
            if self._scope == TargetScope.ORGANIZATION:
                row += f" | {self.metrics.get_template_project_count(template)}"
                row += f" | {self.metrics.get_template_repository_count(template)}"
                row += f" | {self.metrics.get_template_pipeline_count(template)} |"
            elif self._scope == TargetScope.PROJECT:
                row += f" | {self.metrics.get_template_repository_count(template)}"
                row += f" | {self.metrics.get_template_pipeline_count(template)} |"
            elif self._scope == TargetScope.REPOSITORY:
                row += f" | {self.metrics.get_template_pipeline_count(template)} |"
            else:
                row += " |"

            lines.append(row)

        self._write("\n".join(lines))

    def _print_overview(self) -> None:  # pragma: no cover
        """Print hierarchical overview data as Markdown based on scope."""
        lines = [
            f"# {self.result.name}",
            "",
            "## Adoption Summary",
            "",
            f"- Scope: {self._scope.name.title()}",
            f"- Mode: {self.metrics.compliance_mode.name.title()}",
        ]
        if self._scope == TargetScope.PIPELINE:
            lines.append(f"- Status: {'Compliant' if self.result.is_compliant() else 'Non-Compliant'}")
        else:
            lines.append(
                f"- Status: {'Compliant' if self.result.is_compliant(self.metrics.compliance_mode) else 'Non-Compliant'}",
            )
        lines.append(f"- Processing Time: {self.metrics.processing_time:.2f}s")

        # Add rates based on scope
        if self._scope != TargetScope.PIPELINE:
            lines.extend(
                [
                    "",
                    "## Adoption Rates",
                    "",
                ],
            )
            lines.append("| Scope | Rate | Details |")
            lines.append("|--------|------|---------|")

            # Repository and pipeline metrics
            if self._scope == TargetScope.REPOSITORY:
                pipeline_rate = f"{self.result.pipeline_adoption_rate:.1f}%"
                pipeline_detail = f"{len(self.result.compliant_pipelines)}/{self.result.total_no_pipelines}"
                lines.append(f"| Pipeline | {pipeline_rate} | {pipeline_detail} |")

            # Project, repository and pipeline metrics
            elif self._scope == TargetScope.PROJECT:
                repo_rate = f"{self.result.repository_adoption_rate:.1f}%"
                repo_detail = f"{len(self.result.compliant_repositories)}/{self.result.total_no_repositories}"
                pipeline_rate = f"{self.result.pipeline_adoption_rate:.1f}%"
                pipeline_detail = f"{len(self.result.compliant_pipelines)}/{self.result.total_no_pipelines}"

                lines.append(f"| Repository | {repo_rate} | {repo_detail} |")
                lines.append(f"| Pipeline | {pipeline_rate} | {pipeline_detail} |")

            # Organization metrics (all levels)
            elif self._scope == TargetScope.ORGANIZATION:
                project_rate = f"{self.result.project_adoption_rate:.1f}%"
                project_detail = f"{len(self.result.compliant_projects)}/{self.result.total_no_projects}"
                repo_rate = f"{self.result.repository_adoption_rate:.1f}%"
                repo_detail = f"{len(self.result.compliant_repositories)}/{self.result.total_no_repositories}"
                pipeline_rate = f"{self.result.pipeline_adoption_rate:.1f}%"
                pipeline_detail = f"{len(self.result.compliant_pipelines)}/{self.result.total_no_pipelines}"

                lines.append(f"| Project | {project_rate} | {project_detail} |")
                lines.append(f"| Repository | {repo_rate} | {repo_detail} |")
                lines.append(f"| Pipeline | {pipeline_rate} | {pipeline_detail} |")

        # Add template usage statistics
        if self._scope == TargetScope.PIPELINE:
            lines.extend(
                [
                    "",
                    "## Template Statistics",
                    "",
                    f"- Total Templates: {len(self.metrics.template_usage)}",
                    f"- Usage Count: {sum(self.metrics.template_usage.values())}",
                    "",
                    "### Most Used Templates",
                    "",
                    "| Template | Uses |",
                    "|----------|------|",
                ],
            )

            # Add most used templates
            total_uses = sum(self.metrics.template_usage.values())
            for template, count in sorted(
                self.metrics.template_usage.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]:  # Top 3
                lines.append(f"| {template} | {count} |")
        else:
            lines.extend(
                [
                    "",
                    "## Template Statistics",
                    "",
                    f"- Total Templates: {len(self.metrics.template_usage)}",
                    f"- Usage Count: {sum(self.metrics.template_usage.values())}",
                    "",
                    "### Most Used Templates",
                    "",
                    "| Template | Uses | Usage % |",
                    "|----------|------|---------|",
                ],
            )

            # Add most used templates
            total_uses = sum(self.metrics.template_usage.values())
            for template, count in sorted(
                self.metrics.template_usage.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]:  # Top 3
                usage_percent = f"{round(count / total_uses * 100, 2):.2f}%"
                lines.append(f"| `{template}` | {count} | {usage_percent} |")

        self._write("\n".join(lines))

    def _print_non_compliant(self) -> None:  # pragma: no cover  # noqa: C901, PLR0912, PLR0915
        """Print non-compliant items summary as Markdown."""
        lines = [
            f"# {self.result.name}",
            "",
            "## Adoption Summary",
            "",
            f"- Scope: {self._scope.name.title()}",
            f"- Mode: {self.metrics.compliance_mode.name.title()}",
        ]

        # Check Status with appropriate method based on scope
        if self._scope == TargetScope.PIPELINE:
            is_compliant = self.result.is_compliant()
        else:
            is_compliant = self.result.is_compliant(self.metrics.compliance_mode)
        lines.append(f"- Status: {'Compliant' if is_compliant else 'Non-Compliant'}")
        lines.append(f"- Processing Time: {self.metrics.processing_time:.2f}s")

        # Pipeline scope - needs special handling
        if self._scope == TargetScope.PIPELINE:
            self._write("\n".join(lines))
            return

        # Organization scope
        lines.append("")
        if self._scope == TargetScope.ORGANIZATION:
            organization = self.result
            non_compliant_projects = len(organization.non_compliant_projects)
            non_compliant_repos = len(organization.non_compliant_repositories)
            non_compliant_pipelines = len(organization.non_compliant_pipelines)
            lines.extend(
                [
                    "### Non-Compliance Statistics",
                    "",
                    "| Resource Type | Non-Compliant | Total | Rate |",
                    "|---------------|---------------|-------|------|",
                    f"| Projects | {non_compliant_projects} | {organization.total_no_projects} | {organization.project_non_compliance_rate:.1f}% |",
                    f"| Repositories | {non_compliant_repos} | {organization.total_no_repositories} | {organization.repository_non_compliance_rate:.1f}% |",
                    f"| Pipelines | {non_compliant_pipelines} | {organization.total_no_pipelines} | {organization.pipeline_non_compliance_rate:.1f}% |",
                    "",
                ],
            )
            if organization.non_compliant_projects:
                lines.append("### Non-Compliant Projects\n")
                for project in organization.non_compliant_projects:
                    lines.extend([f"- {project.name}"])
                lines.append("")
            if organization.non_compliant_repositories:
                lines.append("### Non-Compliant Repositories\n")
                for repo in organization.non_compliant_repositories:
                    lines.extend([f"- {repo.name}"])
                lines.append("")
            if organization.non_compliant_pipelines:
                lines.append("### Non-Compliant Pipelines\n")
                for pipeline in organization.non_compliant_pipelines:
                    lines.extend([f"- {format_pipeline_path(pipeline)}"])
                lines.append("")

        # Project scope
        elif self._scope == TargetScope.PROJECT:
            project = self.result
            non_compliant_repos = len(project.non_compliant_repositories)
            non_compliant_pipelines = len(project.non_compliant_pipelines)
            lines.extend(
                [
                    "### Non-Compliance Statistics",
                    "",
                    "| Resource Type | Non-Compliant | Total | Rate |",
                    "|---------------|---------------|-------|------|",
                    f"| Repositories | {non_compliant_repos} | {project.total_no_repositories} | {project.repository_non_compliance_rate:.1f}% |",
                    f"| Pipelines | {non_compliant_pipelines} | {project.total_no_pipelines} | {project.pipeline_non_compliance_rate:.1f}% |",
                    "",
                ],
            )
            if project.non_compliant_repositories:
                lines.append("### Non-Compliant Repositories\n")
                for repo in project.non_compliant_repositories:
                    lines.extend([f"- {repo.name}"])
                lines.append("")
            if project.non_compliant_pipelines:
                lines.append("### Non-Compliant Pipelines\n")
                for pipeline in project.non_compliant_pipelines:
                    lines.extend([f"- {format_pipeline_path(pipeline)}"])
                lines.append("")

        # Repository scope
        elif self._scope == TargetScope.REPOSITORY:
            repository = self.result
            non_compliant_pipelines = len(repository.non_compliant_pipelines)
            lines.extend(
                [
                    "### Non-Compliance Statistics",
                    "",
                    "| Resource Type | Non-Compliant | Total | Rate |",
                    "|---------------|---------------|-------|------|",
                    f"| Pipelines | {non_compliant_pipelines} | {repository.total_no_pipelines} | {repository.pipeline_non_compliance_rate:.1f}% |",
                    "",
                ],
            )
            if repository.non_compliant_pipelines:
                lines.append("### Non-Compliant Pipelines\n")
                for pipeline in repository.non_compliant_pipelines:
                    lines.extend([f"- {format_pipeline_path(pipeline)}"])
                lines.append("")

        self._write("\n".join(lines))
