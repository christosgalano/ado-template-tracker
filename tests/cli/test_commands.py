# ruff: noqa: SLF001,PLR2004,C901,PLR0912,S105
import argparse
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ado_template_tracker.cli.commands import (
    create_compliance_mode,
    create_source,
    create_target,
    create_view_mode,
    main,
    parse_args,
    run,
)
from ado_template_tracker.cli.printer import ViewMode
from ado_template_tracker.core.exceptions import (
    InvalidComplianceModeError,
    InvalidViewModeError,
    SourceConfigurationError,
)
from ado_template_tracker.core.models import (
    AdoptionTarget,
    ComplianceMode,
    TemplateSource,
)


@pytest.fixture
def mock_args() -> argparse.Namespace:
    """Create mock command line arguments."""
    args = argparse.Namespace()
    args.organization = "test-org"
    args.token = "test-token"
    args.target_project = "target-project"
    args.target_repository = "target-repo"
    args.target_pipeline_id = None
    args.source_project = "source-project"
    args.source_repository = "source-repo"
    args.source_branch = "main"
    args.source_template = None
    args.source_directories = ["/templates"]
    args.compliance_mode = "any"
    args.output_format = "rich"
    args.output_file = None
    args.output_view = "target"
    return args


def test_create_target() -> None:
    """Test creating AdoptionTarget from CLI arguments."""
    # Test with all arguments
    target = create_target(
        organization="test-org",
        project="test-project",
        repository="test-repo",
        pipeline_id=123,
    )

    if not isinstance(target, AdoptionTarget):
        pytest.fail("Expected AdoptionTarget instance")
    if target.organization != "test-org":
        pytest.fail(f"Expected organization 'test-org', got '{target.organization}'")
    if target.project != "test-project":
        pytest.fail(f"Expected project 'test-project', got '{target.project}'")
    if target.repository != "test-repo":
        pytest.fail(f"Expected repository 'test-repo', got '{target.repository}'")
    if target.pipeline_id != 123:
        pytest.fail(f"Expected pipeline_id 123, got {target.pipeline_id}")

    # Test with minimal arguments
    target = create_target(organization="test-org")
    if target.organization != "test-org":
        pytest.fail(f"Expected organization 'test-org', got '{target.organization}'")
    if target.project is not None:
        pytest.fail(f"Expected project None, got '{target.project}'")
    if target.repository is not None:
        pytest.fail(f"Expected repository None, got '{target.repository}'")
    if target.pipeline_id is not None:
        pytest.fail(f"Expected pipeline_id None, got '{target.pipeline_id}'")


def test_create_source() -> None:
    """Test creating TemplateSource from CLI arguments."""
    # Test with directories
    source = create_source(
        project="test-project",
        repository="test-repo",
        directories=["/templates/steps", "/templates/jobs"],
        branch="develop",
    )
    if not isinstance(source, TemplateSource):
        pytest.fail("Expected TemplateSource instance")
    if source.project != "test-project":
        pytest.fail(f"Expected project 'test-project', got '{source.project}'")
    if source.repository != "test-repo":
        pytest.fail(f"Expected repository 'test-repo', got '{source.repository}'")
    if source.directories != ["/templates/steps", "/templates/jobs"]:
        pytest.fail(f"Expected specific directories, got {source.directories}")
    if source.branch != "develop":
        pytest.fail(f"Expected branch 'develop', got '{source.branch}'")

    # Test with template path
    source = create_source(
        project="test-project",
        repository="test-repo",
        template_path="/templates/main.yaml",
        branch="develop",
    )
    if not isinstance(source, TemplateSource):
        pytest.fail("Expected TemplateSource instance")
    if source.project != "test-project":
        pytest.fail(f"Expected project 'test-project', got '{source.project}'")
    if source.repository != "test-repo":
        pytest.fail(f"Expected repository 'test-repo', got '{source.repository}'")
    if source.template_path != "/templates/main.yaml":
        pytest.fail(f"Expected template_path '/templates/main.yaml', got '{source.template_path}'")
    if source.branch != "develop":
        pytest.fail(f"Expected branch 'develop', got '{source.branch}'")

    # Test with default arguments
    source = create_source(project="test-project", repository="test-repo")
    if source.branch != "main":
        pytest.fail(f"Expected default branch 'main', got '{source.branch}'")
    if source.directories != ["/"]:
        pytest.fail(f"Expected default directories ['/'], got {source.directories}")

    # Test with both template path and directories
    with pytest.raises(SourceConfigurationError, match="Cannot specify both template_path and directories"):
        source = create_source(
            project="test-project",
            repository="test-repo",
            template_path="/templates/main.yaml",
            directories=["/templates/steps", "/templates/jobs"],
            branch="develop",
        )


def test_create_view_mode() -> None:
    """Test creating ViewMode from string."""
    # Test valid modes
    if create_view_mode("target") != ViewMode.TARGET:
        pytest.fail("Expected TARGET view mode")
    if create_view_mode("source") != ViewMode.SOURCE:
        pytest.fail("Expected SOURCE view mode")
    if create_view_mode("overview") != ViewMode.OVERVIEW:
        pytest.fail("Expected OVERVIEW view mode")

    # Test invalid mode
    with pytest.raises(
        InvalidViewModeError,
        match="Invalid view mode: invalid. Must be one of: target, source, overview",
    ):
        create_view_mode("invalid")


def test_create_compliance_mode() -> None:
    """Test creating ComplianceMode from string."""
    # Test valid modes
    if create_compliance_mode("any") != ComplianceMode.ANY:
        pytest.fail("Expected ANY compliance mode")
    if create_compliance_mode("majority") != ComplianceMode.MAJORITY:
        pytest.fail("Expected MAJORITY compliance mode")
    if create_compliance_mode("all") != ComplianceMode.ALL:
        pytest.fail("Expected ALL compliance mode")

    # Test invalid mode
    with pytest.raises(
        InvalidComplianceModeError,
        match="Invalid compliance mode: invalid. Must be one of: any, majority, all",
    ):
        create_compliance_mode("invalid")


def test_parse_args() -> None:
    """Test argument parsing with various inputs."""
    with patch(
        "sys.argv",
        [
            "ado-template-tracker",
            "--organization",
            "test-org",
            "--token",
            "test-token",
            "--target-project",
            "target-project",
            "--target-repository",
            "target-repo",
            "--source-project",
            "source-project",
            "--source-repository",
            "source-repo",
            "--source-branch",
            "develop",
            "--source-directories",
            "/templates/steps",
            "/templates/jobs",
            "--compliance-mode",
            "majority",
            "--output-format",
            "markdown",
            "--output-file",
            "report.md",
            "--output-view",
            "source",
        ],
    ):
        args = parse_args()
        if args.organization != "test-org":
            pytest.fail(f"Expected organization 'test-org', got '{args.organization}'")
        if args.token != "test-token":
            pytest.fail("Token not parsed correctly")
        if args.target_project != "target-project":
            pytest.fail(f"Expected target_project 'target-project', got '{args.target_project}'")
        if args.source_branch != "develop":
            pytest.fail(f"Expected source_branch 'develop', got '{args.source_branch}'")
        if args.source_directories != ["/templates/steps", "/templates/jobs"]:
            pytest.fail(f"Expected source_directories list, got {args.source_directories}")
        if args.compliance_mode != "majority":
            pytest.fail(f"Expected compliance_mode 'majority', got '{args.compliance_mode}'")
        if args.output_format != "markdown":
            pytest.fail(f"Expected output_format 'markdown', got '{args.output_format}'")
        if args.output_file != "report.md":
            pytest.fail(f"Expected output_file 'report.md', got '{args.output_file}'")
        if args.output_view != "source":
            pytest.fail(f"Expected output_view 'source', got '{args.output_view}'")

    # Test mutually exclusive groups
    with (
        patch(
            "sys.argv",
            [
                "ado-template-tracker",
                "--organization",
                "test-org",
                "--source-project",
                "source-project",
                "--source-repository",
                "source-repo",
                "--target-repository",
                "target-repo",
                "--target-pipeline-id",
                "123",
            ],
        ),
        pytest.raises(SystemExit),
    ):
        # Should exit because target-repository and target-pipeline-id are mutually exclusive
        parse_args()

    with (
        patch(
            "sys.argv",
            [
                "ado-template-tracker",
                "--organization",
                "test-org",
                "--source-project",
                "source-project",
                "--source-repository",
                "source-repo",
                "--source-template",
                "/templates/main.yaml",
                "--source-directories",
                "/templates",
            ],
        ),
        pytest.raises(SystemExit),
    ):
        # Should exit because source-template and source-directories are mutually exclusive
        parse_args()


@pytest.mark.asyncio
async def test_run(mock_args: argparse.Namespace) -> None:
    """Test run function with mocked dependencies."""
    # Set up the mocked client with proper async context manager behavior
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client  # Make __aenter__ return itself

    mock_tracker = AsyncMock()
    mock_tracker.track.return_value = (Mock(), Mock())

    mock_printer = Mock()

    with (
        patch("ado_template_tracker.cli.commands.AzureDevOpsClient", return_value=mock_client) as mock_client_class,
        patch(
            "ado_template_tracker.cli.commands.TemplateAdoptionTracker",
            return_value=mock_tracker,
        ) as mock_tracker_class,
        patch("ado_template_tracker.cli.commands.AdoptionRichPrinter", return_value=mock_printer) as mock_printer_class,
    ):
        await run(mock_args)

        # Verify client was created with correct args
        mock_client_class.assert_called_once_with(
            organization=mock_args.organization,
            token=mock_args.token,
        )

        # Verify tracker was created with correct args
        mock_tracker_class.assert_called_once()
        _, kwargs = mock_tracker_class.call_args
        if kwargs["client"] != mock_client:
            pytest.fail("Client not passed correctly to tracker")
        if not isinstance(kwargs["target"], AdoptionTarget):
            pytest.fail("Target not created correctly")
        # Fix: The parameter name is template_source, not source
        if not isinstance(kwargs["template_source"], TemplateSource):
            pytest.fail("Template source not created correctly")
        if kwargs["compliance_mode"] != ComplianceMode.ANY:
            pytest.fail(f"Expected ComplianceMode.ANY, got {kwargs['compliance_mode']}")

        # Verify tracker.track was called
        mock_tracker.track.assert_called_once()

        # Verify printer was created and print was called
        mock_printer_class.assert_called_once()
        mock_printer.print.assert_called_once_with(view_mode=ViewMode.TARGET, output_file=None)


@pytest.mark.asyncio
async def test_run_with_invalid_output_format(mock_args: argparse.Namespace) -> None:
    """Test run function with invalid output format."""
    mock_args.output_format = "invalid"

    # Create AsyncMock objects to handle async context manager and async methods
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client

    mock_tracker = AsyncMock()
    mock_tracker.track.return_value = (Mock(), Mock())  # Return tuple of (result, metrics)

    with (
        patch("ado_template_tracker.cli.commands.AzureDevOpsClient", return_value=mock_client),
        patch("ado_template_tracker.cli.commands.TemplateAdoptionTracker", return_value=mock_tracker),
        pytest.raises(ValueError, match="Invalid output format"),
    ):
        await run(mock_args)


def test_main() -> None:
    """Test main function with mocked dependencies."""
    mock_args = Mock()

    with (
        patch("ado_template_tracker.cli.commands.parse_args", return_value=mock_args) as mock_parse_args,
        patch("ado_template_tracker.cli.commands.asyncio.run") as mock_asyncio_run,
    ):
        main()

        # Verify args were parsed
        mock_parse_args.assert_called_once()

        # Verify asyncio.run was called with run(args)
        mock_asyncio_run.assert_called_once()
        (args,) = mock_asyncio_run.call_args[0]
        # Check that the first arg is a coroutine from run(mock_args)
        if not asyncio.iscoroutine(args):
            pytest.fail("Expected coroutine from run(mock_args)")
