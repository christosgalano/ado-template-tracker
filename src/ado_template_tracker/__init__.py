"""Azure DevOps Template Adoption Tracker.

A tool for tracking and analyzing template adoption in Azure DevOps pipelines
across projects, repositories, and individual pipelines.

Package Structure:
    core: Core functionality for template tracking and API interactions
        - client: Azure DevOps API client with authentication handling
        - models: Data models for resources, configuration, and tracking
        - adoption: Template adoption tracking logic
        - exceptions: Error types for graceful error handling

    cli: Command-line interface components
        - commands: CLI argument parsing and execution
        - printer: Output formatting in various formats (text, JSON, markdown)

    utils: Utility functions and helpers
        - scanner: Repository scanning for YAML files and templates

Components:
    Core API:
        AzureDevOpsClient: API client for Azure DevOps interactions
        TemplateAdoptionTracker: Main component for tracking template adoption
        AdoptionTarget: Configures where to look for template adoption
        TemplateSource: Configures which templates to track

    Resource Models:
        Organization: Azure DevOps organization with adoption metrics
        Project: Project with adoption compliance metrics
        Repository: Repository with template usage metrics
        Pipeline: Pipeline with template references
        Template: Individual template definition

    Configuration Models:
        ComplianceMode: Rules for determining compliance (ANY/MAJORITY/ALL)
        ViewMode: Controls results presentation format (TARGET/SOURCE/OVERVIEW)
        TargetScope: Analysis scope (ORGANIZATION/PROJECT/REPOSITORY/PIPELINE)

Examples:
    CLI Usage:
        ```bash
        # Track template adoption in a project
        $ ado-template-tracker track \\
            --organization myorg \\
            --token mytoken \\
            --source-project Templates \\
            --source-repository PipelineLibrary \\
            --target-project MyProject

        # Use specific output format and compliance mode
        $ ado-template-tracker track \\
            --organization myorg \\
            --source-project Templates \\
            --source-repository PipelineLibrary \\
            --compliance-mode majority \\
            --output-format markdown \\
            --output-file report.md
        ```

    Programmatic Usage:
        ```python
        import os
        from ado_template_tracker import (
            AzureDevOpsClient,
            TemplateAdoptionTracker,
            AdoptionTarget,
            TemplateSource,
            ComplianceMode,
            ViewMode,
        )

        # Configure tracking targets
        target = AdoptionTarget(
            organization=os.getenv("ADO_ORGANIZATION"),
            project="ProjectY",
        )

        source = TemplateSource(
            project="ProjectX",
            repository="pipeline-library",
        )

        # Create and run tracker
        async with AzureDevOpsClient(
            organization=os.getenv("ADO_ORGANIZATION"),
            token=os.getenv("ADO_TOKEN"),
        ) as client:
            tracker = TemplateAdoptionTracker(
                client=client,
                target=target,
                source=source,
                compliance_mode=ComplianceMode.ANY,
            )

            result, metrics = await tracker.track()

            # Use different output formats
            from ado_template_tracker.cli import (
                AdoptionRichPrinter,
                AdoptionJSONPrinter
            )

            printer = AdoptionRichPrinter(result, metrics)
            printer.print(view_mode=ViewMode.TARGET)

            json_printer = AdoptionJSONPrinter(result, metrics)
            json_printer.print(view_mode=ViewMode.SOURCE, output_file="source.json")
        ```
"""

__version__ = "0.1.0"

from ado_template_tracker.core import (
    Adoption,
    AdoptionMetrics,
    AdoptionTarget,
    AzureDevOpsClient,
    ComplianceMode,
    Pipeline,
    Project,
    Repository,
    Template,
    TemplateAdoptionTracker,
    TemplateSource,
    UsageType,
    ViewMode,
)

__all__ = [
    "Adoption",
    "AdoptionMetrics",
    "AdoptionTarget",
    "AzureDevOpsClient",
    "ComplianceMode",
    "Pipeline",
    "Project",
    "Repository",
    "Template",
    "TemplateAdoptionTracker",
    "TemplateSource",
    "UsageType",
    "ViewMode",
    "__version__",
]
