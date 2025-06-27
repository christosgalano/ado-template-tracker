r"""Command-line interface for template tracking.

This module provides the command-line interface functionality for the template tracker.
It handles argument parsing, configuration creation, and execution coordination for
running template adoption analysis from the command line.

Key Components:
    parse_args: Handles CLI argument parsing and validation
    run: Orchestrates the execution of template tracking
    create_target: Creates target configuration from CLI args
    create_source: Creates source configuration from CLI args
    create_view_mode: Converts string to ViewMode enum
    create_compliance_mode: Converts string to ComplianceMode enum
    main: Entry point for CLI execution

Dependencies:
    - core.adoption: Template tracking core functionality
    - core.client: Azure DevOps API client
    - core.models: Configuration data models
    - cli.printer: Results output formatting and presentation

Output Formats:
    - plain: Simple text output suitable for logs and terminals
    - rich: Colorized interactive output with tables and formatting
    - json: Structured JSON output for programmatic consumption
    - markdown: Formatted markdown for documentation and reports

View Modes:
    - target: Results organized by project/repository/pipeline hierarchy
    - source: Results organized by template usage and coverage
    - overview: Overall metrics, trends and compliance status
    - non_compliant: Results filtered to show only non-compliant resources

Example:
    ```python
    from ado_template_tracker.cli.commands import parse_args, run
    import asyncio

    async def main():
        # Parse command line arguments
        args = parse_args()

        # Run template tracking
        await run(args)

        # Or use the synchronous entry point
        asyncio.run(run(args))
    ```

CLI Usage:
    ```bash
    # Basic usage - analyze templates in a project
    $ ado-template-tracker track \
        --organization myorg \
        --token mytoken \
        --source-project Templates \
        --source-repository PipelineLibrary \
        --target-project MyProject

    # Target a specific repository
    $ ado-template-tracker track \
        --organization myorg \
        --source-project Templates \
        --source-repository PipelineLibrary \
        --target-project MyProject \
        --target-repository MyRepo

    # Use different compliance mode and output format
    $ ado-template-tracker track \
        --organization myorg \
        --source-project Templates \
        --source-repository PipelineLibrary \
        --compliance-mode majority \
        --output-format markdown \
        --output-file report.md

    # Use managed identity for authentication
    $ ado-template-tracker track \
        --organization myorg \
        --source-project Templates \
        --source-repository PipelineLibrary

    # Use verbose output for debugging (level INFO)
    $ ado-template-tracker track \
        --organization myorg \
        --token mytoken \
        --source-project Templates \
        --source-repository PipelineLibrary \
        -vv

    # Track non-compliant resources only
    $ ado-template-tracker track \
        --organization myorg \
        --token mytoken \
        --source-project Templates \
        --source-repository PipelineLibrary \
        --output-view non-compliant
    ```

Raises:
    argparse.ArgumentError: When invalid arguments are provided
    AuthenticationError: When Azure DevOps authentication fails
    ValueError: When configuration values are invalid
    InvalidComplianceModeError: When an invalid compliance mode is specified
    InvalidViewModeError: When an invalid view mode is specified
"""

import argparse
import asyncio
import logging
import os

from ado_template_tracker import __version__
from ado_template_tracker.core.adoption import TemplateAdoptionTracker
from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.models import AdoptionTarget, ComplianceMode, TemplateSource

from .printer import (
    AdoptionJSONPrinter,
    AdoptionMarkdownPrinter,
    AdoptionPlainPrinter,
    AdoptionRichPrinter,
    ViewMode,
)


def create_target(
    organization: str,
    project: str | None = None,
    repository: str | None = None,
    pipeline_id: int | None = None,
) -> AdoptionTarget:
    """Creates an AdoptionTarget from CLI arguments."""
    return AdoptionTarget(
        organization=organization,
        project=project,
        repository=repository,
        pipeline_id=pipeline_id,
    )


def create_source(
    project: str,
    repository: str,
    template_path: str | None = None,
    directories: list[str] | None = None,
    branch: str = "main",
) -> TemplateSource:
    """Creates a TemplateSource from CLI arguments."""
    return TemplateSource(
        project=project,
        repository=repository,
        template_path=template_path,
        directories=directories or ["/"],
        branch=branch,
    )


def create_view_mode(view: str) -> ViewMode:
    """Creates a ViewMode from CLI arguments."""
    return ViewMode.from_string(view)


def create_compliance_mode(mode: str) -> ComplianceMode:
    """Creates a ComplianceMode from CLI arguments."""
    return ComplianceMode.from_string(mode)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Track Azure DevOps pipeline template adoption",
    )

    # Azure DevOps connection
    parser.add_argument(
        "--organization",
        required=True,
        help="Azure DevOps organization name",
    )
    parser.add_argument("--token", help="Azure DevOps PAT token")

    # Target configuration
    target_group = parser.add_argument_group(
        "target",
        "Where to look for template adoption",
    )
    target_group.add_argument(
        "--target-project",
        help="Target project name (not setting will target all projects in the organization)",
    )
    target_mutex_group = target_group.add_mutually_exclusive_group()
    target_mutex_group.add_argument(
        "--target-repository",
        help="Optional target repository name (ignored if pipeline ID is provided)",
    )
    target_mutex_group.add_argument(
        "--target-pipeline-id",
        type=int,
        help="Optional target pipeline ID",
    )

    # Template source configuration
    source_group = parser.add_argument_group("source", "Template source configuration")
    source_group.add_argument(
        "--source-project",
        required=True,
        help="Template source project",
    )
    source_group.add_argument(
        "--source-repository",
        required=True,
        help="Template source repository",
    )
    source_group.add_argument(
        "--source-branch",
        default="main",
        help="Template source branch (default: main)",
    )
    source_mutex_group = source_group.add_mutually_exclusive_group()
    source_mutex_group.add_argument(
        "--source-template",
        help="Specific template path to track",
    )
    source_mutex_group.add_argument(
        "--source-directories",
        nargs="+",
        help="List of directories containing templates to track",
    )

    # Compliance mode configuration
    compliance_group = parser.add_argument_group("compliance", "Compliance configuration")
    compliance_group.add_argument(
        "--compliance-mode",
        choices=["any", "majority", "all"],
        default="any",
        help="Compliance mode for template tracking (default: any)",
    )

    # Output configuration
    output_group = parser.add_argument_group("output", "Output configuration")
    output_group.add_argument(
        "--output-format",
        choices=["plain", "rich", "json", "markdown"],
        nargs="+",  # Allow multiple choices
        default=["rich"],  # Default to rich output only
        help="Output format(s) for results (default: rich). Multiple formats can be specified.",
    )
    output_group.add_argument(
        "--output-file",
        default=None,
        help="Output file (only used when a single output format is specified). When multiple formats are requested, "
        "standard outputs are used for plain/rich formats, and adoption-report.[json|md] files are created for "
        "file-based formats.",
    )
    output_group.add_argument(
        "--output-view",
        choices=["target", "source", "overview", "non-compliant"],
        default="target",
        help="Output view to display (default: target)",
    )

    # Add verbosity control
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress all non-essential output",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (can be used multiple times)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{__version__}",
        help="Show the version of the ado-template-tracker",
    )

    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    """Run the adoption tracker with CLI arguments."""
    # Create target and source configurations
    target = create_target(
        organization=args.organization,
        project=args.target_project,
        repository=args.target_repository,
        pipeline_id=args.target_pipeline_id,
    )

    source = create_source(
        project=args.source_project,
        repository=args.source_repository,
        template_path=args.source_template,
        directories=args.source_directories,
        branch=args.source_branch,
    )

    compliance_mode = create_compliance_mode(args.compliance_mode)

    # Create and run tracker
    async with AzureDevOpsClient(
        organization=args.organization,
        token=args.token,
    ) as client:
        tracker = TemplateAdoptionTracker(
            client=client,
            target=target,
            source=source,
            compliance_mode=compliance_mode,
        )

        result, metrics = await tracker.track()

        view_mode = create_view_mode(args.output_view)

        # Handle multiple output formats
        for output_format in args.output_format:
            printer_cls = {
                "plain": AdoptionPlainPrinter,
                "rich": AdoptionRichPrinter,
                "json": AdoptionJSONPrinter,
                "markdown": AdoptionMarkdownPrinter,
            }.get(output_format)

            if printer_cls is None:
                error_message = f"Invalid output format: {output_format}. Must be one of: plain, rich, json, markdown"
                raise ValueError(error_message)

            # And then in the run function, update the comment and logic:
            # Determine output destination based on format and number of requested formats
            output_file = None
            if len(args.output_format) > 1:
                # When multiple formats are requested, ignore any output_file argument
                # and use standard conventions:
                # - plain/rich go to stdout
                # - json/markdown go to default filenames in current directory
                if output_format in ["json", "markdown"]:
                    output_file = f"adoption-report.{output_format}"
                # plain/rich implicitly go to stdout (output_file = None)
            else:
                # Single format requested - respect the output_file if provided
                output_file = args.output_file

                # If no output file is provided but format needs a file, use default naming
                if output_file is None and output_format in ["json", "markdown"]:
                    output_file = f"adoption-report.{output_format}"

            printer = printer_cls(result, metrics)
            printer.print(view_mode=view_mode, output_file=output_file)


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    # First check command-line args
    if hasattr(args, "quiet") and args.quiet:
        log_level = logging.CRITICAL
    elif hasattr(args, "verbose") and args.verbose > 0:
        # Map verbosity count to log levels
        log_level = {
            1: logging.WARNING,
            2: logging.INFO,
            3: logging.DEBUG,
        }.get(min(args.verbose, 3), logging.DEBUG)
    else:
        # Then check environment variable
        env_level = os.environ.get("ADO_TEMPLATE_TRACKER_LOG_LEVEL", "CRITICAL").upper()
        log_level = getattr(logging, env_level, logging.CRITICAL)

    # Configure logging
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Suppress third-party loggers
    logging.getLogger("azure").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)

    asyncio.run(run(args))
