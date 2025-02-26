"""Command line interface for template tracking.

This subpackage provides the command-line interface components for template adoption tracking,
including argument parsing, printer implementations, and execution coordination.

Modules:
    commands: CLI argument parsing and execution
    printer: Output formatting and display

Components:
    Command-line Processing:
        parse_args: Command-line arguments parser
        run: Function to execute tracking with parsed arguments
        main: CLI entry point function
        create_target: Creates target configuration from CLI args
        create_source: Creates source configuration from CLI args
        create_view_mode: Converts string to ViewMode enum
        create_compliance_mode: Converts string to ComplianceMode enum

    Output Formatters:
        AdoptionPrinter: Abstract base printer class
        AdoptionPlainPrinter: Simple text output format
        AdoptionRichPrinter: Rich text console output with tables
        AdoptionJSONPrinter: Structured JSON output format
        AdoptionMarkdownPrinter: GitHub-compatible Markdown output
        ViewMode: Enum controlling result organization format

Example:
    Using from command-line:
    ```bash
    $ ado-template-tracker track --organization myorg --source-project Templates \
        --source-repository MyTemplates --target-project Project1
    ```

    Programmatic usage of CLI components:
    ```python
    from ado_template_tracker.cli import parse_args, run
    import asyncio

    # Run with command-line arguments
    args = parse_args()
    asyncio.run(run(args))
    ```
"""

from ado_template_tracker.cli.commands import (
    create_compliance_mode,
    create_source,
    create_target,
    create_view_mode,
    main,
    parse_args,
    run,
)
from ado_template_tracker.cli.printer import (
    AdoptionJSONPrinter,
    AdoptionMarkdownPrinter,
    AdoptionPlainPrinter,
    AdoptionPrinter,
    AdoptionRichPrinter,
    ViewMode,
)

__all__ = [  # noqa: RUF022
    # Command-line processing
    "create_source",
    "create_target",
    "create_view_mode",
    "create_compliance_mode",
    "parse_args",
    "run",
    "main",
    # Output formatters
    "AdoptionJSONPrinter",
    "AdoptionMarkdownPrinter",
    "AdoptionPlainPrinter",
    "AdoptionPrinter",
    "AdoptionRichPrinter",
    "ViewMode",
]
