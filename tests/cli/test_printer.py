# ruff: noqa: SLF001,PLR2004,C901,PLR0912,S105,SIM117
from pathlib import Path

import pytest

from ado_template_tracker.cli.printer import (
    AdoptionPlainPrinter,
    format_pipeline_path,
    format_template_path,
)
from ado_template_tracker.core.exceptions import InvalidViewModeError
from ado_template_tracker.core.models import (
    Adoption,
    AdoptionMetrics,
    AdoptionTarget,
    ComplianceMode,
    Organization,
    Pipeline,
    Project,
    Repository,
    Template,
    UsageType,
    ViewMode,
)


@pytest.fixture
def template() -> Template:
    """Create a sample template."""
    return Template(
        name="test-template.yaml",
        path="templates/steps/test-template.yaml",
        repository="pipeline-templates",
        project="Pipeline-Library",
    )


@pytest.fixture
def pipeline() -> Pipeline:
    """Create a sample pipeline."""
    template = Template(
        name="test-template.yaml",
        path="templates/steps/test-template.yaml",
        repository="pipeline-templates",
        project="Pipeline-Library",
    )

    adoption = Adoption(
        usage_type=UsageType.INCLUDE,
        templates=[template],
    )

    return Pipeline(
        id=123,
        name="test-pipeline.yml",
        folder="src\\pipelines",
        path="src/pipelines/test-pipeline.yml",
        project_id="project1",
        repository_id="repo1",
        content="trigger:\n  - main\n",
        adoption=adoption,
    )


@pytest.fixture
def repository(pipeline: Pipeline) -> Repository:
    """Create a sample repository."""
    repo = Repository(
        id="repo1",
        name="test-repo",
        default_branch="main",
        project_id="project1",
    )
    repo.compliant_pipelines = [pipeline]
    repo.total_no_pipelines = 2
    return repo


@pytest.fixture
def project(repository: Repository) -> Project:
    """Create a sample project."""
    project = Project(
        id="project1",
        name="Test Project",
    )
    project.compliant_repositories = [repository]
    project.total_no_repositories = 2
    project.compliant_pipelines = repository.compliant_pipelines
    project.total_no_pipelines = repository.total_no_pipelines
    return project


@pytest.fixture
def organization(project: Project) -> Organization:
    """Create a sample organization."""
    org = Organization(name="TestOrg")
    org.compliant_projects = [project]
    org.total_no_projects = 2
    org.compliant_repositories = project.compliant_repositories
    org.total_no_repositories = project.total_no_repositories
    org.compliant_pipelines = project.compliant_pipelines
    org.total_no_pipelines = project.total_no_pipelines
    return org


@pytest.fixture
def metrics() -> AdoptionMetrics:
    """Create sample adoption metrics."""
    target = AdoptionTarget(organization="TestOrg")
    metrics = AdoptionMetrics(target=target, compliance_mode=ComplianceMode.ANY)

    # Add template usage data
    metrics.add_template_usage(
        template="templates/steps/test-template.yaml",
        project="Test Project",
        repository="test-repo",
        pipeline="test-pipeline.yml",
    )
    metrics.add_template_usage(
        template="templates/jobs/another-template.yaml",
        project="Test Project",
        repository="test-repo",
        pipeline="another-pipeline.yml",
    )

    metrics.processing_time = 1.5
    return metrics


def test_format_template_path(template: Template) -> None:
    """Test the format_template_path helper function."""
    expected = "pipeline-templates/templates/steps/test-template.yaml"
    result = format_template_path(template)
    if result != expected:
        pytest.fail(f"Expected template path '{expected}', got '{result}'")


def test_format_pipeline_path(pipeline: Pipeline) -> None:
    """Test the format_pipeline_path helper function."""
    expected = "src/pipelines/test-pipeline.yml"
    result = format_pipeline_path(pipeline)
    if result != expected:
        pytest.fail(f"Expected pipeline path '{expected}', got '{result}'")


def test_invalid_view_mode(organization: Organization, metrics: AdoptionMetrics) -> None:
    """Test handling of invalid view mode."""
    printer = AdoptionPlainPrinter(organization, metrics)

    # Create an invalid ViewMode value
    invalid_view = "INVALID_VIEW"

    with pytest.raises(InvalidViewModeError):
        printer.print(view_mode=invalid_view)


def test_get_output_stream(organization: Organization, metrics: AdoptionMetrics, tmp_path: Path) -> None:
    """Test the _get_output_stream method in various scenarios."""
    printer = AdoptionPlainPrinter(organization, metrics)

    # Skip direct stdout testing as it conflicts with pytest's capturing
    # Just test the file output functionality which is easier to verify

    # Test with file path
    output_file = str(tmp_path / "test_output.txt")
    test_content = "Test content"

    # Use a separate function to handle the context manager
    # to avoid conflicts with pytest's output capturing
    def write_to_file() -> None:
        with printer._get_output_stream(output_file) as stream:
            stream.write(test_content)

    # Execute the function
    write_to_file()

    # Verify file was created and contains the content
    output_path = Path(output_file)
    if not output_path.exists():
        pytest.fail(f"Output file {output_file} was not created")

    content = output_path.read_text()
    if content != test_content:
        pytest.fail(f"Expected content '{test_content}', got '{content}'")

    # Test with invalid path
    invalid_path = str(tmp_path / "nonexistent" / "file.txt")
    with pytest.raises((FileNotFoundError, OSError, IOError)):
        # Just test that opening fails without using context manager
        printer._get_output_stream(invalid_path)


def test_with_file_output(
    organization: Organization,
    metrics: AdoptionMetrics,
    tmp_path: Path,
) -> None:
    """Test printer with file output."""
    output_file = str(tmp_path / "output.txt")

    printer = AdoptionPlainPrinter(organization, metrics)
    printer.print(view_mode=ViewMode.OVERVIEW, output_file=output_file)

    # Verify file was created
    output_path = Path(output_file)
    if not output_path.exists():
        pytest.fail(f"Output file {output_file} was not created")

    # Verify file contains content
    content = output_path.read_text()
    if "Adoption Statistics Overview" not in content:
        pytest.fail("Expected overview content in output file")
    if organization.name not in content:
        pytest.fail(f"Expected organization name '{organization.name}' in output file")
