from enum import Enum
from typing import Union

from model import AdoptionMetrics, Pipeline, Project, Repository, Template
from rich.console import Console
from rich.table import Table

console = Console()


class ViewMode(Enum):
    """Represents different ways to view adoption data."""

    TARGET = "target"  # View by project/repository/pipeline
    TEMPLATE = "template"  # View by template usage
    STATISTICS = "stats"  # Overall statistics view


def print_adoption_results(
    result: Union[Project, Repository, Pipeline],
    metrics: AdoptionMetrics,
    view_mode: ViewMode = ViewMode.TARGET,
) -> None:
    """
    Print adoption results in specified view mode.

    Args:
        result: The target object (Project, Repository, or Pipeline)
        metrics: Adoption metrics to display
        view_mode: How to display the results (target/template/stats)
    """
    if view_mode == ViewMode.TARGET:
        print_target_view(result, metrics)
    elif view_mode == ViewMode.TEMPLATE:
        print_template_view(metrics)
    else:
        print_statistics_view(metrics)


def print_target_view(
    result: Union[Project, Repository, Pipeline], metrics: AdoptionMetrics
) -> None:
    """Print detailed view of target adoption."""
    if isinstance(result, Project):
        print_project_adoption(result, metrics)
    elif isinstance(result, Repository):
        print_repository_adoption(result, metrics)
    elif isinstance(result, Pipeline):
        print_pipeline_adoption(result, metrics)
    else:
        raise ValueError(f"Unsupported result type: {type(result)}")


def print_template_view(metrics: AdoptionMetrics) -> None:
    """Print template-centric view of adoption."""
    table = Table(title="Template Usage Analysis")

    table.add_column("Template", style="cyan")
    table.add_column("Usage Count", style="green", justify="right")
    table.add_column("Usage %", style="yellow", justify="right")
    table.add_column("Projects", style="blue", justify="right")
    table.add_column("Repositories", style="magenta", justify="right")

    total_uses = sum(metrics.template_usage.values())

    for template, count in sorted(
        metrics.template_usage.items(), key=lambda x: x[1], reverse=True
    ):
        usage_percent = count / total_uses * 100
        table.add_row(
            template,
            str(count),
            f"{usage_percent:.1f}%",
            str(metrics.get_template_project_count(template)),
            str(metrics.get_template_repository_count(template)),
        )

    console.print(table)


def print_statistics_view(metrics: AdoptionMetrics) -> None:
    """Print overall statistics and trends."""
    table = Table(title="Adoption Statistics Overview")

    # Summary section
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Details", style="yellow")

    # Overall adoption
    table.add_row(
        "Overall Adoption",
        f"{metrics.pipeline_adoption_rate:.1f}%",
        f"{metrics.compliant_pipelines} of {metrics.total_pipelines} pipelines",
    )

    # Repository coverage
    if metrics.total_repositories > 0:
        table.add_row(
            "Repository Coverage",
            f"{metrics.repository_adoption_rate:.1f}%",
            f"{metrics.compliant_repositories} of {metrics.total_repositories} repositories",
        )

    table.add_section()

    # Template statistics
    table.add_row(
        "[bold]Template Statistics[/bold]",
        f"{len(metrics.template_usage)} templates",
        f"{sum(metrics.template_usage.values())} total uses",
    )

    # Most used templates (top 3)
    top_templates = sorted(
        metrics.template_usage.items(), key=lambda x: x[1], reverse=True
    )[:3]

    for template, count in top_templates:
        usage_percent = count / metrics.compliant_pipelines * 100
        table.add_row(
            f"├─ {template}", str(count), f"{usage_percent:.1f}% of compliant pipelines"
        )

    # Performance metrics
    table.add_section()
    table.add_row("Processing Time", f"{metrics.processing_time:.2f}s", "")

    console.print(table)


def format_template_path(template: Template) -> str:
    """Formats a template path in the format project/repository/path."""
    return f"{template.repository}/{template.path}"


def format_pipeline_path(pipeline: Pipeline) -> str:
    """Formats a pipeline path in the format project/repository/path."""
    return f"{pipeline.folder}/{pipeline.name}".replace("\\", "/")


def print_project_adoption(project: Project, metrics: AdoptionMetrics) -> None:
    """Print adoption report for an entire project with metrics."""
    table = Table(
        title=(
            f"Project '{project.name}' - Compliant Repositories: "
            f"{metrics.compliant_repositories} of {metrics.total_repositories} "
            f"({metrics.repository_adoption_rate:.1f}% adoption rate)"
        )
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
                template_paths = [
                    format_template_path(t) for t in pipeline.adoption.templates
                ]
                # Update template usage metrics
                for template in pipeline.adoption.templates:
                    metrics.add_template_usage(template.path, project.name, repo.name)

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
                f"{len(repo.compliant_pipelines)}/{repo.total_no_pipelines} "
                f"({len(repo.compliant_pipelines) / repo.total_no_pipelines * 100:.1f}%)"
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

    console.print(table)
    print_metrics_summary(metrics)


def print_repository_adoption(repository: Repository, metrics: AdoptionMetrics) -> None:
    """Print adoption report for a specific repository with metrics."""
    table = Table(
        title=(
            f"Repository '{repository.name}' - Compliant Pipelines: "
            f"{metrics.compliant_pipelines} of {metrics.total_pipelines} "
            f"({metrics.pipeline_adoption_rate:.1f}% adoption rate)"
        )
    )
    table.add_column("Pipeline", style="cyan")
    table.add_column("Template(s)", style="blue")
    table.add_column("Usage", style="magenta", justify="center")

    for pipeline in repository.compliant_pipelines:
        if pipeline.adoption:
            template_paths = [
                format_template_path(t) for t in pipeline.adoption.templates
            ]
            # Update template usage metrics
            for template in pipeline.adoption.templates:
                metrics.add_template_usage(template.path, repository=repository.name)

            table.add_row(
                format_pipeline_path(pipeline),
                "\n".join(template_paths),
                pipeline.adoption.usage_type.value,
            )

    console.print(table)
    print_metrics_summary(metrics)


def print_pipeline_adoption(pipeline: Pipeline, metrics: AdoptionMetrics) -> None:
    """Print adoption report for a specific pipeline with metrics."""
    table = Table(
        title=(
            f"Pipeline '{pipeline.name}' Adoption "
            f"({'Compliant' if metrics.compliant_pipelines > 0 else 'Non-compliant'})"
        )
    )

    table.add_column("Template", style="cyan")
    table.add_column("Usage", style="magenta", justify="center")
    table.add_column("Template Usage", style="yellow", justify="right")

    if pipeline.adoption:
        for template in pipeline.adoption.templates:
            usage_count = metrics.template_usage.get(template.path, 0)
            table.add_row(
                template.path,
                pipeline.adoption.usage_type.value,
                f"Used in {usage_count} pipeline(s)",
            )

    console.print(table)
    print_metrics_summary(metrics)


def print_metrics_summary(metrics: AdoptionMetrics) -> None:
    """Print a concise metrics summary."""
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")

    if metrics.template_usage:
        top_templates = sorted(
            metrics.template_usage.items(), key=lambda x: x[1], reverse=True
        )[:3]
        summary_table.add_row(
            "Most Used Templates:",
            ", ".join(f"{t} ({c} uses)" for t, c in top_templates),
        )

    summary_table.add_row("Processing Time:", f"{metrics.processing_time:.2f}s")

    console.print("\n[bold]Additional Metrics[/bold]")
    console.print(summary_table)
