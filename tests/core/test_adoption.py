# ruff: noqa: SLF001,PLR2004,C901,PLR0912,PLR0915,PLR0913
import asyncio
import logging
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
import yaml

from ado_template_tracker.core.adoption import TemplateAdoptionTracker
from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.exceptions import InitializationError, InvalidClientError, SourceConfigurationError
from ado_template_tracker.core.models import (
    Adoption,
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
)


### Fixtures ###
@pytest.fixture
def template_factory():
    """Factory fixture to create template objects with consistent defaults."""

    def _create_template(
        name="test-template.yaml",
        path=None,
        repository="pipeline-templates",
        project="Pipeline-Library",
    ) -> Template:
        if path is None:
            path = f"templates/steps/{name}"
        return Template(name=name, path=path, repository=repository, project=project)

    return _create_template


@pytest.fixture
def pipeline_factory():
    """Factory fixture to create pipeline objects with consistent defaults."""

    def _create_pipeline(
        pid=101,
        name="test-pipeline.yml",
        folder="src",
        path=None,
        repository_id="repo1",
        project_id="project1",
        content=None,
        templates=None,
        usage_type=UsageType.INCLUDE,
    ) -> Pipeline:
        if path is None:
            path = f"{folder}/{name}"

        adoption = None
        if templates:
            adoption = Adoption(usage_type=usage_type, templates=templates)

        return Pipeline(
            id=pid,
            name=name,
            folder=folder,
            path=path,
            repository_id=repository_id,
            project_id=project_id,
            content=content,
            adoption=adoption,
        )

    return _create_pipeline


@pytest.fixture
def repository_factory():
    """Factory fixture to create repository objects with consistent defaults."""

    def _create_repository(
        rid="repo1",
        name="test-repo",
        default_branch="main",
        project_id="project1",
        compliant_pipelines=None,
        total_no_pipelines=None,
    ):
        repo = Repository(
            id=rid,
            name=name,
            default_branch=default_branch,
            project_id=project_id,
        )

        if compliant_pipelines is not None:
            repo.compliant_pipelines = compliant_pipelines

        if total_no_pipelines is not None:
            repo.total_no_pipelines = total_no_pipelines

        return repo

    return _create_repository


@pytest.fixture
def sample_stages_template() -> str:
    """Sample template YAML with parameters and stages."""
    # template/stages/dotnet-ci.yaml
    content = {
        "parameters": {
            "solution": {
                "type": "string",
                "default": "**/*.sln",
            },
            "testProjects": {
                "type": "object",
                "default": ["**/*.Tests.csproj"],
            },
        },
        "stages": [
            {
                "stage": "Build",
                "jobs": [
                    {
                        "job": "BuildSolution",
                        "steps": [
                            {
                                "task": "DotNetCoreCLI@2",
                                "inputs": {
                                    "command": "build",
                                    "projects": "${{ parameters.solution }}",
                                },
                            },
                        ],
                    },
                ],
            },
            {
                "stage": "Test",
                "jobs": [
                    {
                        "job": "RunTests",
                        "steps": [
                            {
                                "task": "DotNetCoreCLI@2",
                                "inputs": {
                                    "command": "test",
                                    "projects": "${{ join(',', parameters.testProjects) }}",
                                    "publishTestResults": True,
                                },
                            },
                        ],
                    },
                ],
            },
        ],
    }
    return yaml.dump(content)


@pytest.fixture
def sample_jobs_template() -> str:
    """Sample template YAML with parameters and jobs."""
    # templates/jobs/dotnet-ci.yaml
    content = {
        "parameters": {
            "solution": {
                "type": "string",
                "default": "**/*.sln",
            },
            "testProjects": {
                "type": "object",
                "default": ["**/*.Tests.csproj"],
            },
        },
        "jobs": [
            {
                "job": "BuildSolution",
                "steps": [
                    {
                        "task": "DotNetCoreCLI@2",
                        "inputs": {
                            "command": "build",
                            "projects": "${{ parameters.solution }}",
                        },
                    },
                ],
            },
            {
                "job": "RunTests",
                "steps": [
                    {
                        "task": "DotNetCoreCLI@2",
                        "inputs": {
                            "command": "test",
                            "projects": "${{ join(',', parameters.testProjects) }}",
                            "publishTestResults": True,
                        },
                    },
                ],
            },
        ],
    }
    return yaml.dump(content)


@pytest.fixture
def sample_steps_template() -> str:
    """Sample template YAML with parameters and steps."""
    # template/steps/dotnet-ci.yaml
    content = {
        "parameters": {
            "solution": {
                "type": "string",
                "default": "**/*.sln",
            },
            "testProjects": {
                "type": "object",
                "default": ["**/*.Tests.csproj"],
            },
        },
        "steps": [
            {
                "task": "DotNetCoreCLI@2",
                "inputs": {
                    "command": "build",
                    "projects": "${{ parameters.solution }}",
                },
            },
            {
                "task": "DotNetCoreCLI@2",
                "inputs": {
                    "command": "test",
                    "projects": "${{ join(',', parameters.testProjects) }}",
                    "publishTestResults": True,
                },
            },
        ],
    }
    return yaml.dump(content)


@pytest.fixture
def sample_pipeline_with_includes() -> str:
    """Sample pipeline using template includes."""
    content = {
        "trigger": ["main"],
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Pipeline-Library/pipeline-templates",
                    "ref": "refs/heads/main",
                },
            ],
        },
        "stages": [
            {
                "stage": "Build",
                "jobs": [
                    {
                        "job": "CI with steps",
                        "steps": [
                            {
                                "template": "templates/steps/dotnet-ci.yaml@templates",
                                "parameters": {
                                    "solution": "src/MySolution.sln",
                                },
                            },
                        ],
                    },
                    {
                        "template": "templates/jobs/dotnet-ci.yaml@templates",
                        "parameters": {
                            "solution": "src/MySolution.sln",
                            "testProjects": ["tests/**/*.Tests.csproj"],
                        },
                    },
                ],
            },
        ],
    }
    return yaml.dump(content)


@pytest.fixture
def sample_pipeline_with_extend() -> str:
    """Sample pipeline using template extension."""
    content = {
        "trigger": ["main", "develop"],
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Pipeline-Library/pipeline-templates",
                    "ref": "refs/heads/main",
                },
            ],
        },
        "variables": {
            "buildConfiguration": "Release",
            "dotnetVersion": "7.0.x",
        },
        "extends": {
            "template": "templates/stages/dotnet-ci.yaml@templates",
            "parameters": {
                "solution": "src/MySolution.sln",
                "testProjects": ["tests/**/*.Tests.csproj"],
            },
        },
    }
    return yaml.dump(content)


@pytest.fixture
def sample_non_compliant_pipeline() -> str:
    """Sample pipeline with no template usage."""
    content = {
        "trigger": ["main"],
        "stages": [
            {
                "stage": "Build",
                "jobs": [
                    {
                        "job": "BuildSolution",
                        "steps": [
                            {
                                "task": "DotNetCoreCLI@2",
                                "inputs": {
                                    "command": "build",
                                    "projects": "**/*.sln",
                                },
                            },
                        ],
                    },
                    {
                        "job": "RunTests",
                        "steps": [
                            {
                                "task": "DotNetCoreCLI@2",
                                "inputs": {
                                    "command": "test",
                                    "projects": "**/*.Tests.csproj",
                                    "publishTestResults": True,
                                },
                            },
                        ],
                    },
                ],
            },
        ],
    }
    return yaml.dump(content)


@pytest.fixture
def source_reference() -> dict:
    """Create a standard source reference for templates."""
    return {
        "alias": "templates",
        "project": "Pipeline-Library",
        "repository": "pipeline-templates",
        "ref": "refs/heads/main",
    }


@pytest.fixture
def mock_client() -> Mock:
    """Create a mock Azure DevOps client."""
    client = Mock(spec=AzureDevOpsClient)

    # Set basic mock properties
    organization = "TestOrg"
    client.base_url = f"https://dev.azure.com/{organization}"

    # Mock API responses
    client._get.return_value = {"defaultBranch": "refs/heads/main"}

    return client


@pytest.fixture
def mock_scanner(
    sample_steps_template: str,
    sample_jobs_template: str,
    sample_stages_template: str,
) -> Generator[AsyncMock, None, None]:
    """Create a mock repository scanner with realistic template content."""
    with patch("ado_template_tracker.core.adoption.RepositoryScanner") as mock:
        scanner = AsyncMock()
        scanner.scan = AsyncMock(
            return_value=[
                ("templates/steps/dotnet-ci.yaml", sample_steps_template),
                ("templates/jobs/dotnet-ci.yaml", sample_jobs_template),
                ("templates/stages/dotnet-ci.yaml", sample_stages_template),
            ],
        )
        mock.return_value = scanner
        yield scanner


@pytest.fixture
def tracker(mock_client) -> TemplateAdoptionTracker:
    """Create a template adoption tracker for testing."""
    return TemplateAdoptionTracker(
        client=mock_client,
        target=AdoptionTarget(
            organization="TestOrg",
            project="Test-Project",
        ),
        source=TemplateSource(
            project="Pipeline-Library",
            repository="pipeline-templates",
            branch="main",
        ),
        compliance_mode=ComplianceMode.ANY,
    )


@pytest_asyncio.fixture
async def initialized_tracker(
    tracker: TemplateAdoptionTracker,
    mock_client: Mock,
    sample_pipeline_with_includes: str,
    sample_pipeline_with_extend: str,
    sample_non_compliant_pipeline: str,
) -> TemplateAdoptionTracker:
    """Create and initialize tracker with sample pipelines."""
    # Create test pipelines
    include_pipeline = Pipeline(
        id=1,
        name="include-pipeline.yaml",
        folder="src",
        path="src/include-pipeline.yaml",
        content=sample_pipeline_with_includes,
        repository_id="repo1",
        project_id="project1",
    )

    extend_pipeline = Pipeline(
        id=2,
        name="extend-pipeline.yml",
        folder="src",
        path="src/extend-pipeline.yml",
        content=sample_pipeline_with_extend,
        repository_id="repo1",
        project_id="project1",
    )

    non_compliant_pipeline_1 = Pipeline(
        id=3,
        name="non-compliant-pipeline.yml",
        folder="src",
        path="src/non-compliant-pipeline.yml",
        content=sample_non_compliant_pipeline,
        repository_id="repo1",
        project_id="project1",
    )

    non_compliant_pipeline_2 = Pipeline(
        id=4,
        name="non-compliant-pipeline-2.yml",
        folder="src",
        path="src/non-compliant-pipeline.yml",
        content=sample_non_compliant_pipeline,
        repository_id="repo2",
        project_id="project1",
    )

    # Mock client responses
    pipelines = [include_pipeline, extend_pipeline, non_compliant_pipeline_1, non_compliant_pipeline_2]
    mock_client.list_pipelines_async.return_value = pipelines
    mock_client._get_async.return_value = {"value": []}

    # Set up source templates
    tracker.source.templates = [
        "templates/steps/dotnet-ci.yaml",
        "templates/jobs/dotnet-ci.yaml",
        "templates/stages/dotnet-ci.yaml",
    ]

    # Mock repository API response
    mock_client._get.return_value = {
        "defaultBranch": "refs/heads/main",
        "name": "pipeline-templates",
        "project": {"name": "Pipeline-Library"},
    }

    # Initialize tracker
    await tracker.setup()

    if not tracker._initialized:
        pytest.fail("Expected tracker to be initialized")

    if len(tracker._all_pipelines) != len(pipelines):
        pytest.fail(f"Expected {len(pipelines)} project pipelines to be initialized")

    return tracker


### Initialization Tests ###
@pytest.mark.asyncio
async def test_setup(tracker: TemplateAdoptionTracker, mock_client: Mock) -> None:
    """Test basic tracker initialization."""
    # Setup - mock async methods needed for initialization
    mock_client.list_pipelines_async.return_value = []
    mock_client._get_async.return_value = {"value": []}

    # Test initialization
    await tracker.setup()

    # Check source configuration matches expected values
    if tracker.source.repository != "pipeline-templates":
        pytest.fail(f"Expected source repository to be 'pipeline-templates', got '{tracker.source.repository}'")
    if tracker.source.project != "Pipeline-Library":
        pytest.fail(f"Expected source project to be 'Pipeline-Library', got '{tracker.source.project}'")

    # Check target configuration
    if tracker.target.project != "Test-Project":
        pytest.fail(f"Expected target project to be 'Test-Project', got '{tracker.target.project}'")

    # Check pipeline state
    if tracker._all_pipelines:
        pytest.fail("Expected empty pipelines")

    # Verify API interactions
    mock_client.list_pipelines_async.assert_called_once_with("Test-Project")


def test_tracker_initialization_with_invalid_client() -> None:
    """Test tracker initialization with invalid client."""
    with pytest.raises(InvalidClientError):
        TemplateAdoptionTracker(
            client="not a client",
            source=TemplateSource(project="p", repository="r"),
            target=AdoptionTarget(organization="o", project="p"),
        )


def test_tracker_initialization_with_missing_source_repo(mock_client: Mock) -> None:
    """Test tracker initialization with missing source repository."""
    with pytest.raises(SourceConfigurationError):
        TemplateAdoptionTracker(
            client=mock_client,
            source=TemplateSource(project="p", repository=""),
            target=AdoptionTarget(organization="o", project="p"),
        )


### Core Logic Tests ###
@pytest.mark.asyncio
async def test_set_compliance(initialized_tracker: TemplateAdoptionTracker) -> None:
    """Test that _set_compliance correctly updates compliance information across all levels."""
    # Create test data structure with projects, repositories, and pipelines
    project1 = Project(id="project1", name="Project-1")
    project2 = Project(id="project2", name="Project-2")

    repo1 = Repository(id="repo1", name="Repo-1", project_id="project1", default_branch="main")
    repo2 = Repository(id="repo2", name="Repo-2", project_id="project1", default_branch="main")
    repo3 = Repository(id="repo3", name="Repo-3", project_id="project2", default_branch="main")

    # Create pipelines with different compliance statuses
    adoption = Adoption(
        usage_type=UsageType.EXTEND,
        templates=[
            TemplateSource(
                project="Pipeline-Library",
                repository="pipeline-templates",
                template_path="templates/steps/dotnet-ci.yaml",
            ),
        ],
    )

    pipeline1 = Pipeline(
        id=101,
        name="p1",
        folder="ci",
        repository_id="repo1",
        project_id="project1",
        adoption=adoption,
    )
    pipeline2 = Pipeline(id=102, name="p2", folder="ci", repository_id="repo1", project_id="project1", adoption=None)
    pipeline3 = Pipeline(
        id=103,
        name="p3",
        folder="ci",
        repository_id="repo2",
        project_id="project1",
        adoption=adoption,
    )
    pipeline4 = Pipeline(id=104, name="p4", folder="ci", repository_id="repo3", project_id="project2", adoption=None)
    pipeline5 = Pipeline(
        id=105,
        name="p5",
        folder="ci",
        repository_id="repo3",
        project_id="project2",
        adoption=adoption,
    )

    # Set up the tracker with our test data
    initialized_tracker._all_projects = [project1, project2]
    initialized_tracker._all_repositories = [repo1, repo2, repo3]
    initialized_tracker._all_pipelines = [pipeline1, pipeline2, pipeline3, pipeline4, pipeline5]

    # Define compliant pipelines (those where is_compliant returns True)
    compliant_pipelines = [pipeline1, pipeline3, pipeline5]

    # Call the method under test
    initialized_tracker._set_compliance(compliant_pipelines)

    # Verify repositories have correct compliance data
    # Repo1 should have 1 compliant pipeline out of 2 total
    if len(repo1.compliant_pipelines) != 1:
        pytest.fail(f"Expected repo1 to have 1 compliant pipeline, got {len(repo1.compliant_pipelines)}")
    if repo1.total_no_pipelines != 2:
        pytest.fail(f"Expected repo1 to have 2 total pipelines, got {repo1.total_no_pipelines}")
    if repo1.compliant_pipelines[0].id != 101:
        pytest.fail(f"Expected pipeline 101 to be compliant in repo1, got {repo1.compliant_pipelines[0].id}")

    # Repo2 should have 1 compliant pipeline out of 1 total
    if len(repo2.compliant_pipelines) != 1:
        pytest.fail(f"Expected repo2 to have 1 compliant pipeline, got {len(repo2.compliant_pipelines)}")
    if repo2.total_no_pipelines != 1:
        pytest.fail(f"Expected repo2 to have 1 total pipeline, got {repo2.total_no_pipelines}")

    # Repo3 should have 1 compliant pipeline out of 2 total
    if len(repo3.compliant_pipelines) != 1:
        pytest.fail(f"Expected repo3 to have 1 compliant pipeline, got {len(repo3.compliant_pipelines)}")
    if repo3.total_no_pipelines != 2:
        pytest.fail(f"Expected repo3 to have 2 total pipelines, got {repo3.total_no_pipelines}")

    # Verify projects have correct compliance data
    # Project1 should have 2 compliant pipelines out of 3 total
    if len(project1.compliant_pipelines) != 2:
        pytest.fail(f"Expected project1 to have 2 compliant pipelines, got {len(project1.compliant_pipelines)}")
    if project1.total_no_pipelines != 3:
        pytest.fail(f"Expected project1 to have 3 total pipelines, got {project1.total_no_pipelines}")

    # Project1 should have 2 repositories and both should be compliant with ANY mode
    if project1.total_no_repositories != 2:
        pytest.fail(f"Expected project1 to have 2 repositories, got {project1.total_no_repositories}")

    # With ANY compliance mode, both repositories in project1 should be compliant
    initialized_tracker.compliance_mode = ComplianceMode.ANY
    if len(project1.compliant_repositories) != 2:
        pytest.fail(
            f"Expected project1 to have 2 compliant repositories with ANY mode, got {len(project1.compliant_repositories)}",  # noqa: E501
        )

    # Project2 should have 1 compliant pipeline out of 2 total
    if len(project2.compliant_pipelines) != 1:
        pytest.fail(f"Expected project2 to have 1 compliant pipeline, got {len(project2.compliant_pipelines)}")
    if project2.total_no_pipelines != 2:
        pytest.fail(f"Expected project2 to have 2 total pipelines, got {project2.total_no_pipelines}")

    # Test with different compliance mode
    initialized_tracker.compliance_mode = ComplianceMode.ALL
    # Re-run compliance calculation
    initialized_tracker._set_compliance(compliant_pipelines)

    # With ALL compliance mode, repo1 should not be compliant (only 1 of 2 pipelines)
    if len(project1.compliant_repositories) != 1:
        pytest.fail(
            f"Expected project1 to have 1 compliant repository with ALL mode, got {len(project1.compliant_repositories)}",  # noqa: E501
        )
    if repo2 not in project1.compliant_repositories:
        pytest.fail("Expected repo2 to be compliant with ALL mode")


@pytest.mark.asyncio
async def test_create_result(initialized_tracker: TemplateAdoptionTracker) -> None:
    """Test that _create_result correctly creates appropriate result objects based on target scope."""

    # Test PIPELINE scope
    initialized_tracker.target_scope = TargetScope.PIPELINE
    pipeline = Pipeline(
        id=101,
        name="test-pipeline.yml",
        folder="src",
        path="src/test-pipeline.yml",
        repository_id="repo1",
        project_id="project1",
    )
    initialized_tracker._all_pipelines = [pipeline]

    result = initialized_tracker._create_result()
    if not isinstance(result, Pipeline):
        pytest.fail(f"Expected Pipeline result for PIPELINE scope, got {type(result).__name__}")
    if result.id != 101:
        pytest.fail(f"Expected pipeline ID 101, got {result.id}")

    # Test REPOSITORY scope
    initialized_tracker.target_scope = TargetScope.REPOSITORY
    repo = Repository(
        id="repo1",
        name="test-repo",
        default_branch="main",
        project_id="project1",
    )
    initialized_tracker._all_repositories = [repo]

    result = initialized_tracker._create_result()
    if not isinstance(result, Repository):
        pytest.fail(f"Expected Repository result for REPOSITORY scope, got {type(result).__name__}")
    if result.id != "repo1":
        pytest.fail(f"Expected repository ID 'repo1', got '{result.id}'")

    # Test PROJECT scope
    initialized_tracker.target_scope = TargetScope.PROJECT
    project = Project(
        id="project1",
        name="test-project",
    )
    initialized_tracker._all_projects = [project]

    result = initialized_tracker._create_result()
    if not isinstance(result, Project):
        pytest.fail(f"Expected Project result for PROJECT scope, got {type(result).__name__}")
    if result.name != "test-project":
        pytest.fail(f"Expected project name 'test-project', got '{result.name}'")

    # Test ORGANIZATION scope
    initialized_tracker.target_scope = TargetScope.ORGANIZATION

    # Set up projects, repositories, and pipelines with compliance data
    project1 = Project(id="project1", name="project1")
    project1.compliant_pipelines = [pipeline]
    project1.total_no_pipelines = 2
    project1.compliant_repositories = [repo]
    project1.total_no_repositories = 2

    repo.compliant_pipelines = [pipeline]
    repo.total_no_pipelines = 1

    pipeline.adoption = Adoption(
        usage_type=UsageType.INCLUDE,
        templates=[Template(name="t1", path="p1", repository="r1", project="p1")],
    )

    initialized_tracker._all_projects = [project1]
    initialized_tracker._all_repositories = [repo]
    initialized_tracker._all_pipelines = [pipeline]
    initialized_tracker._compliant_pipelines = [pipeline]

    result = initialized_tracker._create_result()
    if not isinstance(result, Organization):
        pytest.fail(f"Expected Organization result for ORGANIZATION scope, got {type(result).__name__}")
    if result.name != "TestOrg":
        pytest.fail(f"Expected organization name 'TestOrg', got '{result.name}'")
    if result.total_no_projects != 1:
        pytest.fail(f"Expected 1 project, got {result.total_no_projects}")
    if result.total_no_repositories != 1:
        pytest.fail(f"Expected 1 repository, got {result.total_no_repositories}")
    if result.total_no_pipelines != 1:
        pytest.fail(f"Expected 1 pipeline, got {result.total_no_pipelines}")
    if len(result.compliant_pipelines) != 1:
        pytest.fail(f"Expected 1 compliant pipeline, got {len(result.compliant_pipelines)}")

    # Test error cases
    # Multiple projects for PROJECT scope
    initialized_tracker.target_scope = TargetScope.PROJECT
    initialized_tracker._all_projects = [Project(id="p1", name="p1"), Project(id="p2", name="p2")]
    with pytest.raises(InitializationError):
        initialized_tracker._create_result()

    # Multiple repositories for REPOSITORY scope
    initialized_tracker.target_scope = TargetScope.REPOSITORY
    initialized_tracker._all_repositories = [
        Repository(id="r1", name="r1", default_branch="main", project_id="p1"),
        Repository(id="r2", name="r2", default_branch="main", project_id="p1"),
    ]
    with pytest.raises(InitializationError):
        initialized_tracker._create_result()

    # No pipelines for PIPELINE scope
    initialized_tracker.target_scope = TargetScope.PIPELINE
    initialized_tracker._all_pipelines = []
    with pytest.raises(InitializationError):
        initialized_tracker._create_result()


@pytest.mark.asyncio
async def test_process_pipelines(
    initialized_tracker: TemplateAdoptionTracker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _process_pipelines processes all pipelines with concurrency limit."""
    # Create a list of test pipelines
    test_pipelines = [
        Pipeline(
            id=i,
            name=f"pipeline-{i}",
            folder="src",
            path=f"src/pipeline-{i}.yml",
            content=f"# Pipeline {i} content",
            repository_id="repo1",
            project_id="project1",
        )
        for i in range(15)  # More than MAX_CONCURRENT_PROCESSING
    ]

    # Keep track of concurrently executing tasks
    currently_running = 0
    max_concurrent = 0
    processed_pipelines = []

    # Use a real semaphore in our test to properly control concurrency
    test_semaphore = asyncio.Semaphore(initialized_tracker.MAX_CONCURRENT_PROCESSING)

    # Mock the process_pipeline method to track calls
    async def mock_process_pipeline(pipeline) -> Pipeline:
        nonlocal currently_running, max_concurrent, processed_pipelines

        # Use the real semaphore in our mock to control concurrency
        async with test_semaphore:
            # Track concurrency inside the semaphore
            currently_running += 1
            max_concurrent = max(max_concurrent, currently_running)
            processed_pipelines.append(pipeline)

            # Add a small delay to ensure concurrent processing is visible
            await asyncio.sleep(0.01)

            # Set adoption data on the pipeline
            pipeline.adoption = Adoption(
                usage_type=UsageType.INCLUDE,
                templates=[
                    Template(
                        name="test-template.yaml",
                        path="templates/test-template.yaml",
                        repository="pipeline-templates",
                        project="Pipeline-Library",
                    ),
                ],
            )

            # Decrease count before returning
            currently_running -= 1
            return pipeline

    # Apply patch only to the process_pipeline method
    monkeypatch.setattr(initialized_tracker, "_process_pipeline", mock_process_pipeline)

    # Run the method under test
    result_pipelines = await initialized_tracker._process_pipelines(test_pipelines)

    # Verify concurrency limit was respected
    if max_concurrent > initialized_tracker.MAX_CONCURRENT_PROCESSING:
        pytest.fail(
            f"Concurrency limit exceeded: {max_concurrent} > {initialized_tracker.MAX_CONCURRENT_PROCESSING}",
        )

    # Verify all pipelines were processed
    if len(processed_pipelines) != len(test_pipelines):
        pytest.fail(f"Expected {len(test_pipelines)} pipelines to be processed, got {len(processed_pipelines)}")

    # Verify each pipeline was processed exactly once
    processed_ids = [p.id for p in processed_pipelines]
    if len(processed_ids) != len(set(processed_ids)):
        pytest.fail("Some pipelines were processed more than once")

    # Verify all pipelines were returned with adoption data
    if len(result_pipelines) != len(test_pipelines):
        pytest.fail(f"Expected {len(test_pipelines)} pipelines in result, got {len(result_pipelines)}")

    # Verify each returned pipeline has adoption data
    for pipeline in result_pipelines:
        if pipeline.adoption is None:
            pytest.fail(f"Pipeline {pipeline.id} is missing adoption data")


@pytest.mark.asyncio
async def test_process_pipeline(initialized_tracker: TemplateAdoptionTracker) -> None:
    """Test template adoption tracking for both include and extend patterns."""
    # Process include pipeline
    include_pipeline = initialized_tracker._all_pipelines[0]
    processed_include = await initialized_tracker._process_pipeline(include_pipeline)

    # Process extend pipeline
    extend_pipeline = initialized_tracker._all_pipelines[1]
    processed_extend = await initialized_tracker._process_pipeline(extend_pipeline)

    # Verify include pipeline
    if processed_include.adoption is None:
        pytest.fail("Include pipeline adoption is None")

    if processed_include.adoption.usage_type != UsageType.INCLUDE:
        pytest.fail(f"Expected usage type {UsageType.INCLUDE!s}, got '{processed_include.adoption.usage_type}'")

    template_count = len(processed_include.adoption.templates)
    if template_count != 2:
        pytest.fail(f"Expected 2 templates, got {template_count}")

    template_paths = [t.path for t in processed_include.adoption.templates]
    if "templates/steps/dotnet-ci.yaml" not in template_paths:
        pytest.fail("Missing expected template: templates/steps/dotnet-ci.yaml")
    if "templates/jobs/dotnet-ci.yaml" not in template_paths:
        pytest.fail("Missing expected template: templates/jobs/dotnet-ci.yaml")

    # Verify extend pipeline
    if processed_extend.adoption is None:
        pytest.fail("Extend pipeline adoption is None")

    if processed_extend.adoption.usage_type != UsageType.EXTEND:
        pytest.fail(f"Expected usage type {UsageType.EXTEND!s}, got '{processed_extend.adoption.usage_type}'")

    if len(processed_extend.adoption.templates) != 1:
        pytest.fail(f"Expected 1 template, got {len(processed_extend.adoption.templates)}")

    if processed_extend.adoption.templates[0].path != "templates/stages/dotnet-ci.yaml":
        pytest.fail(
            f"Expected template path 'templates/stages/dotnet-ci.yaml', "
            f"got '{processed_extend.adoption.templates[0].path}'",
        )


@pytest.mark.asyncio
async def test_parse_pipeline_content(initialized_tracker: TemplateAdoptionTracker) -> None:
    """Test pipeline content parsing to detect template usage patterns."""
    # Setup source templates for testing
    initialized_tracker.source.templates = [
        "templates/steps/dotnet-ci.yaml",
        "templates/jobs/dotnet-ci.yaml",
        "templates/stages/dotnet-ci.yaml",
        "templates/steps/custom-template.yaml",
    ]

    # Test 1: Pipeline with extends template
    extends_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/main

    extends:
      template: templates/stages/dotnet-ci.yaml@templates
    """

    result = initialized_tracker._parse_pipeline_content("test-extends.yml", extends_content)
    if result is None:
        pytest.fail("Expected Adoption object for extends template, got None")
    if result.usage_type != UsageType.EXTEND:
        pytest.fail(f"Expected UsageType.EXTEND, got {result.usage_type}")
    if len(result.templates) != 1:
        pytest.fail(f"Expected 1 template, got {len(result.templates)}")
    if result.templates[0].path != "templates/stages/dotnet-ci.yaml":
        pytest.fail(f"Expected path 'templates/stages/dotnet-ci.yaml', got {result.templates[0].path}")

    # Test 2: Pipeline with include templates
    include_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/main

    steps:
      - template: templates/steps/dotnet-ci.yaml@templates
      - template: templates/steps/custom-template.yaml@templates
      - script: echo "Regular step"
    """

    result = initialized_tracker._parse_pipeline_content("test-include.yml", include_content)
    if result is None:
        pytest.fail("Expected Adoption object for include templates, got None")
    if result.usage_type != UsageType.INCLUDE:
        pytest.fail(f"Expected UsageType.INCLUDE, got {result.usage_type}")
    if len(result.templates) != 2:
        pytest.fail(f"Expected 2 templates, got {len(result.templates)}")

    template_paths = [t.path for t in result.templates]
    if "templates/steps/dotnet-ci.yaml" not in template_paths:
        pytest.fail("Missing expected template: templates/steps/dotnet-ci.yaml")
    if "templates/steps/custom-template.yaml" not in template_paths:
        pytest.fail("Missing expected template: templates/steps/custom-template.yaml")

    # Test 3: Pipeline with mismatched branch
    wrong_branch_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/develop  # Different from source branch (main)

    extends:
      template: templates/stages/dotnet-ci.yaml@templates
    """

    result = initialized_tracker._parse_pipeline_content("test-wrong-branch.yml", wrong_branch_content)
    if result is not None:
        pytest.fail(f"Expected None for mismatched branch, got {result}")

    # Test 4: Pipeline with no templates
    no_templates_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/main

    steps:
      - script: echo "Regular step"
    """

    result = initialized_tracker._parse_pipeline_content("test-no-templates.yml", no_templates_content)
    if result is not None:
        pytest.fail(f"Expected None for pipeline with no templates, got {result}")

    # Test 5: Pipeline with invalid YAML
    invalid_yaml_content = """
    invalid:
      - yaml:
          content: [
    """

    result = initialized_tracker._parse_pipeline_content("test-invalid-yaml.yml", invalid_yaml_content)
    if result is not None:
        pytest.fail(f"Expected None for invalid YAML, got {result}")

    # Test 6: Pipeline with different repository
    diff_repo_content = """
    resources:
      repositories:
        - repository: other_templates
          type: git
          name: Different-Project/different-templates
          ref: refs/heads/main

    extends:
      template: templates/stages/dotnet-ci.yaml@other_templates
    """

    result = initialized_tracker._parse_pipeline_content("test-diff-repo.yml", diff_repo_content)
    if result is not None:
        pytest.fail(f"Expected None for different repository, got {result}")

    # Test 7: Pipeline with template but invalid alias
    wrong_alias_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/main

    steps:
      - template: templates/steps/dotnet-ci.yaml@wrong_alias
    """

    result = initialized_tracker._parse_pipeline_content("test-wrong-alias.yml", wrong_alias_content)
    if result is not None:
        pytest.fail(f"Expected None for wrong template alias, got {result}")

    # Test 8: Pipeline with template not in source templates
    unknown_template_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/main

    steps:
      - template: templates/steps/unknown-template.yaml@templates
    """

    result = initialized_tracker._parse_pipeline_content("test-unknown-template.yml", unknown_template_content)
    if result is not None:
        pytest.fail(f"Expected None for unknown template, got {result}")


@pytest.mark.asyncio
async def test_find_source_reference(
    initialized_tracker: TemplateAdoptionTracker,
    mock_client: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    """Test pipeline source repository reference parsing and validation."""

    # Mock the default branch retrieval method
    monkeypatch.setattr(
        initialized_tracker,
        "_get_source_repository_default_branch",
        lambda: "main",
    )

    # Test case 1: Valid source reference with explicit branch
    valid_pipeline_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Pipeline-Library/pipeline-templates",
                    "ref": "refs/heads/main",
                },
            ],
        },
    }

    result = initialized_tracker._find_source_reference(valid_pipeline_def, "test-pipeline.yml")
    if result is None:
        pytest.fail("Expected valid source reference, got None")
    if result["alias"] != "templates":
        pytest.fail(f"Expected alias 'templates', got {result['alias']}")
    if result["project"] != "Pipeline-Library":
        pytest.fail(f"Expected project 'Pipeline-Library', got {result['project']}")
    if result["repository"] != "pipeline-templates":
        pytest.fail(f"Expected repository 'pipeline-templates', got {result['repository']}")

    # Test case 2: Valid source reference with default branch
    valid_default_branch_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Pipeline-Library/pipeline-templates",
                    # No ref specified, should use default branch
                },
            ],
        },
    }

    result = initialized_tracker._find_source_reference(valid_default_branch_def, "test-pipeline.yml")
    if result is None:
        pytest.fail("Expected valid source reference with default branch, got None")
    if result["ref"] != "refs/heads/main":
        pytest.fail(f"Expected ref 'refs/heads/main', got {result['ref']}")

    # Test case 3: No resources section
    no_resources_def = {"steps": [{"script": "echo hello"}]}
    result = initialized_tracker._find_source_reference(no_resources_def, "test-pipeline.yml")
    if result is not None:
        pytest.fail(f"Expected None for missing resources, got {result}")

    # Test case 4: Invalid resources format (not a dict)
    invalid_resources_def = {"resources": "not a dict"}
    result = initialized_tracker._find_source_reference(invalid_resources_def, "test-pipeline.yml")
    if result is not None:
        pytest.fail(f"Expected None for invalid resources format, got {result}")

    # Test case 5: No repositories in resources
    no_repos_def = {"resources": {}}
    result = initialized_tracker._find_source_reference(no_repos_def, "test-pipeline.yml")
    if result is not None:
        pytest.fail(f"Expected None for no repositories, got {result}")

    # Test case 6: Repository not of type 'git'
    non_git_repo_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "tfsgit",
                    "name": "Pipeline-Library/pipeline-templates",
                },
            ],
        },
    }

    result = initialized_tracker._find_source_reference(non_git_repo_def, "test-pipeline.yml")
    if result is not None:
        pytest.fail(f"Expected None for non-git repository, got {result}")

    # Test case 7: Missing repository name
    missing_name_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                },
            ],
        },
    }

    result = initialized_tracker._find_source_reference(missing_name_def, "test-pipeline.yml")
    if result is not None:
        pytest.fail(f"Expected None for missing repository name, got {result}")

    # Test case 8: Repository without project prefix (uses target project)
    repo_without_project_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "pipeline-templates",  # No project prefix
                    "ref": "refs/heads/main",
                },
            ],
        },
    }

    # Create a NEW tracker with target project matching source project for this test
    special_tracker = TemplateAdoptionTracker(
        client=mock_client,
        target=AdoptionTarget(
            organization="TestOrg",
            project="Pipeline-Library",  # Set to match the source project
        ),
        source=TemplateSource(
            project="Pipeline-Library",
            repository="pipeline-templates",
            branch="main",
        ),
        compliance_mode=ComplianceMode.ANY,
    )

    # Apply the same mock to this tracker
    monkeypatch.setattr(
        special_tracker,
        "_get_source_repository_default_branch",
        lambda: "main",
    )

    result = special_tracker._find_source_reference(repo_without_project_def, "test-pipeline.yml")

    if result is None:
        pytest.fail("Expected valid source reference without project prefix, got None")
    if result["project"] != "Pipeline-Library":
        pytest.fail(f"Expected project 'Pipeline-Library', got {result['project']}")

    # Test case 9: Repository name doesn't match source
    wrong_repo_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Different-Project/different-templates",
                    "ref": "refs/heads/main",
                },
            ],
        },
    }

    result = initialized_tracker._find_source_reference(wrong_repo_def, "test-pipeline.yml")
    if result is not None:
        pytest.fail(f"Expected None for mismatched repository, got {result}")

    # Test case 10: Branch doesn't match source
    wrong_branch_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Pipeline-Library/pipeline-templates",
                    "ref": "refs/heads/develop",  # Different branch
                },
            ],
        },
    }

    with caplog.at_level(logging.WARNING):
        result = initialized_tracker._find_source_reference(wrong_branch_def, "test-pipeline.yml")

    if result is not None:
        pytest.fail(f"Expected None for mismatched branch, got {result}")

    # Test case 11: Multiple repositories with one valid
    multiple_repos_def = {
        "resources": {
            "repositories": [
                {
                    "repository": "other_repo",
                    "type": "git",
                    "name": "Different-Project/different-templates",
                },
                {
                    "repository": "templates",
                    "type": "git",
                    "name": "Pipeline-Library/pipeline-templates",
                    "ref": "refs/heads/main",
                },
            ],
        },
    }

    result = initialized_tracker._find_source_reference(multiple_repos_def, "test-pipeline.yml")
    if result is None:
        pytest.fail("Expected valid source reference with multiple repositories, got None")
    if result["alias"] != "templates":
        pytest.fail(f"Expected alias 'templates', got {result['alias']}")


@pytest.mark.asyncio
async def test_find_extend_template(
    initialized_tracker: TemplateAdoptionTracker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test finding and validating extended templates in pipeline definitions."""
    # Set up source reference for tests
    source_reference = {
        "alias": "templates",
        "project": "Pipeline-Library",
        "repository": "pipeline-templates",
        "ref": "refs/heads/main",
    }

    # Mock _create_template to return a predictable Template object
    def mock_create_template(template_path, _):
        if template_path == "templates/stages/dotnet-ci.yaml@templates":
            return Template(
                name="dotnet-ci.yaml",
                path="templates/stages/dotnet-ci.yaml",
                repository="pipeline-templates",
                project="Pipeline-Library",
            )
        return None

    monkeypatch.setattr(initialized_tracker, "_create_template", mock_create_template)

    # Test 1: Valid extends template
    valid_extends_def = {
        "extends": {
            "template": "templates/stages/dotnet-ci.yaml@templates",
        },
    }

    result = initialized_tracker._find_extend_template(valid_extends_def, source_reference)
    if result is None:
        pytest.fail("Expected a Template object for valid extends definition, got None")
    if result.path != "templates/stages/dotnet-ci.yaml":
        pytest.fail(f"Expected template path 'templates/stages/dotnet-ci.yaml', got '{result.path}'")
    if result.name != "dotnet-ci.yaml":
        pytest.fail(f"Expected template name 'dotnet-ci.yaml', got '{result.name}'")

    # Test 2: No extends section
    no_extends_def = {
        "steps": [
            {"script": "echo 'Hello World'"},
        ],
    }

    result = initialized_tracker._find_extend_template(no_extends_def, source_reference)
    if result is not None:
        pytest.fail(f"Expected None for pipeline without extends section, got {result}")

    # Test 3: Extends section with wrong type (not a dict)
    invalid_extends_type_def = {
        "extends": "not a dictionary",
    }

    result = initialized_tracker._find_extend_template(invalid_extends_type_def, source_reference)
    if result is not None:
        pytest.fail(f"Expected None for invalid extends type, got {result}")

    # Test 4: Extends dictionary without template key
    missing_template_def = {
        "extends": {
            "something_else": "value",
        },
    }

    result = initialized_tracker._find_extend_template(missing_template_def, source_reference)
    if result is not None:
        pytest.fail(f"Expected None for extends without template key, got {result}")

    # Test 5: _create_template returns None (template not found or invalid)
    invalid_template_def = {
        "extends": {
            "template": "invalid/template.yaml@templates",
        },
    }

    result = initialized_tracker._find_extend_template(invalid_template_def, source_reference)
    if result is not None:
        pytest.fail(f"Expected None for invalid template path, got {result}")

    # Test 6: Extends with empty template string
    empty_template_def = {
        "extends": {
            "template": "",
        },
    }

    result = initialized_tracker._find_extend_template(empty_template_def, source_reference)
    if result is not None:
        pytest.fail(f"Expected None for empty template string, got {result}")


@pytest.mark.asyncio
async def test_find_include_templates(
    initialized_tracker: TemplateAdoptionTracker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test finding and validating included templates in pipeline definitions."""
    # Set up source reference for tests
    source_reference = {
        "alias": "templates",
        "project": "Pipeline-Library",
        "repository": "pipeline-templates",
        "ref": "refs/heads/main",
    }

    # Mock _create_template to return predictable Template objects
    def mock_create_template(template_path, source_ref) -> Template | None:  # noqa: ARG001
        valid_paths = {
            "templates/steps/dotnet-ci.yaml@templates": Template(
                name="dotnet-ci.yaml",
                path="templates/steps/dotnet-ci.yaml",
                repository="pipeline-templates",
                project="Pipeline-Library",
            ),
            "templates/jobs/build.yaml@templates": Template(
                name="build.yaml",
                path="templates/jobs/build.yaml",
                repository="pipeline-templates",
                project="Pipeline-Library",
            ),
            "templates/stages/release.yaml@templates": Template(
                name="release.yaml",
                path="templates/stages/release.yaml",
                repository="pipeline-templates",
                project="Pipeline-Library",
            ),
        }
        return valid_paths.get(template_path)

    monkeypatch.setattr(initialized_tracker, "_create_template", mock_create_template)

    # Test 1: Pipeline with templates in different sections
    multi_section_def = {
        "steps": [
            {"template": "templates/steps/dotnet-ci.yaml@templates"},
            {"script": "echo 'Direct step'"},
        ],
        "jobs": [
            {"job": "build", "template": "templates/jobs/build.yaml@templates"},
            {"job": "test", "steps": [{"script": "echo 'Test'"}]},
        ],
        "stages": [
            {"stage": "release", "template": "templates/stages/release.yaml@templates"},
            {"stage": "deploy", "jobs": [{"job": "deploy", "steps": [{"script": "echo 'Deploy'"}]}]},
        ],
    }

    results = initialized_tracker._find_include_templates(multi_section_def, source_reference)
    if len(results) != 3:
        pytest.fail(f"Expected 3 templates, got {len(results)}")

    template_paths = [t.path for t in results]
    if "templates/steps/dotnet-ci.yaml" not in template_paths:
        pytest.fail("Missing template: templates/steps/dotnet-ci.yaml")
    if "templates/jobs/build.yaml" not in template_paths:
        pytest.fail("Missing template: templates/jobs/build.yaml")
    if "templates/stages/release.yaml" not in template_paths:
        pytest.fail("Missing template: templates/stages/release.yaml")

    # Test 2: Pipeline with no templates
    no_templates_def = {
        "steps": [
            {"script": "echo 'Step 1'"},
            {"script": "echo 'Step 2'"},
        ],
        "jobs": [
            {"job": "test", "steps": [{"script": "echo 'Test'"}]},
        ],
    }

    results = initialized_tracker._find_include_templates(no_templates_def, source_reference)
    if results:
        pytest.fail(f"Expected no templates, got {len(results)}")

    # Test 3: Pipeline with invalid template paths
    invalid_templates_def = {
        "steps": [
            {"template": "invalid/path.yaml@templates"},
        ],
    }

    results = initialized_tracker._find_include_templates(invalid_templates_def, source_reference)
    if results:
        pytest.fail(f"Expected no valid templates from invalid paths, got {len(results)}")

    # Test 4: Pipeline with templates from different repository
    wrong_repo_def = {
        "steps": [
            {"template": "templates/steps/dotnet-ci.yaml@other_repo"},
        ],
    }

    results = initialized_tracker._find_include_templates(wrong_repo_def, source_reference)
    if results:
        pytest.fail(f"Expected no templates from wrong repository, got {len(results)}")

    # Test 5: Pipeline with deeply nested templates
    nested_templates_def = {
        "stages": [
            {
                "stage": "build",
                "jobs": [
                    {
                        "job": "compile",
                        "steps": [
                            {"template": "templates/steps/dotnet-ci.yaml@templates"},
                        ],
                    },
                ],
            },
        ],
    }

    results = initialized_tracker._find_include_templates(nested_templates_def, source_reference)
    if len(results) != 1:
        pytest.fail(f"Expected 1 template from nested structure, got {len(results)}")
    if results[0].path != "templates/steps/dotnet-ci.yaml":
        pytest.fail(f"Expected path 'templates/steps/dotnet-ci.yaml', got '{results[0].path}'")

    # Test 6: Pipeline with mixed valid and invalid templates
    mixed_templates_def = {
        "steps": [
            {"template": "templates/steps/dotnet-ci.yaml@templates"},
            {"template": "invalid/path.yaml@templates"},
            {"template": "templates/jobs/build.yaml@wrong_repo"},
        ],
    }

    results = initialized_tracker._find_include_templates(mixed_templates_def, source_reference)
    if len(results) != 1:
        pytest.fail(f"Expected 1 valid template from mixed set, got {len(results)}")
    if results[0].path != "templates/steps/dotnet-ci.yaml":
        pytest.fail(f"Expected path 'templates/steps/dotnet-ci.yaml', got '{results[0].path}'")

    # Test 7: Non-dictionary pipeline definition
    non_dict_def = "not a dictionary"

    results = initialized_tracker._find_include_templates(non_dict_def, source_reference)
    if results:
        pytest.fail(f"Expected no templates from non-dictionary definition, got {len(results)}")

    # Test 8: None pipeline definition
    results = initialized_tracker._find_include_templates(None, source_reference)
    if results:
        pytest.fail(f"Expected no templates from None definition, got {len(results)}")

    # Test 9: Empty dictionary
    empty_def = {}

    results = initialized_tracker._find_include_templates(empty_def, source_reference)
    if results:
        pytest.fail(f"Expected no templates from empty dictionary, got {len(results)}")


@pytest.mark.asyncio
async def test_find_template_references(initialized_tracker: TemplateAdoptionTracker) -> None:
    """Test recursive discovery of template references in pipeline definitions."""

    # Test 1: Simple dictionary with direct template reference
    simple_def = {
        "steps": [
            {"template": "templates/steps/test.yaml@templates"},
        ],
    }

    results = initialized_tracker._find_template_references(simple_def)
    if len(results) != 1:
        pytest.fail(f"Expected 1 template reference, got {len(results)}")
    if results[0] != "templates/steps/test.yaml@templates":
        pytest.fail(f"Expected 'templates/steps/test.yaml@templates', got '{results[0]}'")

    # Test 2: Deep nesting with multiple templates at different levels
    nested_def = {
        "stages": [
            {
                "stage": "build",
                "jobs": [
                    {
                        "job": "compile",
                        "steps": [
                            {"template": "templates/steps/build.yaml@templates"},
                            {"script": "echo 'Direct step'"},
                        ],
                    },
                ],
            },
            {
                "stage": "test",
                "jobs": [
                    {
                        "template": "templates/jobs/test.yaml@templates",
                    },
                ],
            },
        ],
        "extends": {
            "template": "templates/base.yaml@templates",
        },
    }

    results = initialized_tracker._find_template_references(nested_def)
    if len(results) != 3:
        pytest.fail(f"Expected 3 template references, got {len(results)}")
    expected_templates = [
        "templates/steps/build.yaml@templates",
        "templates/jobs/test.yaml@templates",
        "templates/base.yaml@templates",
    ]
    for template in expected_templates:
        if template not in results:
            pytest.fail(f"Expected template reference '{template}' not found in results")

    # Test 3: Template without repository reference (should be filtered out)
    local_template_def = {
        "steps": [
            {"template": "local-template.yaml"},
            {"template": "templates/steps/remote.yaml@templates"},
        ],
    }

    results = initialized_tracker._find_template_references(local_template_def)
    if len(results) != 1:
        pytest.fail(f"Expected 1 template reference (local template filtered), got {len(results)}")
    if results[0] != "templates/steps/remote.yaml@templates":
        pytest.fail(f"Expected 'templates/steps/remote.yaml@templates', got '{results[0]}'")

    # Test 4: List input
    list_def = [
        {"template": "templates/one.yaml@templates"},
        {"script": "echo 'test'"},
        {"template": "templates/two.yaml@templates"},
    ]

    results = initialized_tracker._find_template_references(list_def)
    if len(results) != 2:
        pytest.fail(f"Expected 2 template references, got {len(results)}")

    # Test 5: Mixed structure with templates in lists and dictionaries
    mixed_def = {
        "jobs": [
            {"template": "templates/jobs/job1.yaml@templates"},
            {
                "job": "custom",
                "steps": [
                    {"template": "templates/steps/step1.yaml@templates"},
                    {"template": "templates/steps/step2.yaml@templates"},
                ],
            },
        ],
        "variables": {
            "template": "variables.yaml",  # No @ symbol, should be filtered
        },
    }

    results = initialized_tracker._find_template_references(mixed_def)
    if len(results) != 3:
        pytest.fail(f"Expected 3 template references, got {len(results)}")

    # Test 6: Empty and non-dictionary inputs
    # Empty dict
    results = initialized_tracker._find_template_references({})
    if results:
        pytest.fail(f"Expected no template references for empty dict, got {len(results)}")

    # Empty list
    results = initialized_tracker._find_template_references([])
    if results:
        pytest.fail(f"Expected no template references for empty list, got {len(results)}")

    # None
    results = initialized_tracker._find_template_references(None)
    if results:
        pytest.fail(f"Expected no template references for None, got {len(results)}")

    # String
    results = initialized_tracker._find_template_references("not a dict or list")
    if results:
        pytest.fail(f"Expected no template references for string input, got {len(results)}")


@pytest.mark.asyncio
async def test_create_template(
    initialized_tracker: TemplateAdoptionTracker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test creation and validation of template objects from path references."""
    # Set up source templates for testing
    initialized_tracker.source.templates = [
        "templates/steps/build.yaml",
        "templates/jobs/test.yaml",
        "templates/stages/deploy.yaml",
    ]

    # Set up source reference
    source_reference = {
        "alias": "templates",
        "project": "Pipeline-Library",
        "repository": "pipeline-templates",
        "ref": "refs/heads/main",
    }

    # Test 1: Valid template path with correct reference
    result = initialized_tracker._create_template(
        "templates/steps/build.yaml@templates",
        source_reference,
    )
    if result is None:
        pytest.fail("Expected a valid Template object, got None")
    if result.name != "build.yaml":
        pytest.fail(f"Expected template name 'build.yaml', got '{result.name}'")
    if result.path != "templates/steps/build.yaml":
        pytest.fail(f"Expected path 'templates/steps/build.yaml', got '{result.path}'")
    if result.repository != "pipeline-templates":
        pytest.fail(f"Expected repository 'pipeline-templates', got '{result.repository}'")
    if result.project != "Pipeline-Library":
        pytest.fail(f"Expected project 'Pipeline-Library', got '{result.project}'")

    # Test 2: Template path without @ symbol
    with caplog.at_level(logging.DEBUG):
        result = initialized_tracker._create_template(
            "templates/steps/build.yaml",
            source_reference,
        )
    if result is not None:
        pytest.fail(f"Expected None for template without @ symbol, got {result}")
    if "skipping template without repository reference" not in caplog.text:
        pytest.fail("Expected debug log for missing repository reference")

    # Test 3: Template path not in source templates
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        result = initialized_tracker._create_template(
            "templates/steps/unknown.yaml@templates",
            source_reference,
        )
    if result is not None:
        pytest.fail(f"Expected None for unknown template path, got {result}")
    if "skipping template not found in source" not in caplog.text:
        pytest.fail("Expected debug log for template not found in source")

    # Test 4: Template with wrong alias
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result = initialized_tracker._create_template(
            "templates/steps/build.yaml@wrong_alias",
            source_reference,
        )
    if result is not None:
        pytest.fail(f"Expected None for template with wrong alias, got {result}")
    if "no repository reference found for alias" not in caplog.text:
        pytest.fail("Expected warning log for wrong alias")

    # Test 5: Multiple valid templates
    results = []
    for template_path in [
        "templates/steps/build.yaml@templates",
        "templates/jobs/test.yaml@templates",
        "templates/stages/deploy.yaml@templates",
    ]:
        template = initialized_tracker._create_template(template_path, source_reference)
        if template:
            results.append(template)

    if len(results) != 3:
        pytest.fail(f"Expected 3 valid templates, got {len(results)}")

    # Test 6: Empty template path
    result = initialized_tracker._create_template("@templates", source_reference)
    if result is not None:
        pytest.fail(f"Expected None for empty template path, got {result}")

    # Test 7: Empty alias
    result = initialized_tracker._create_template("templates/steps/build.yaml@", source_reference)
    if result is not None:
        pytest.fail(f"Expected None for empty alias, got {result}")


### Metrics Tests ###
def assert_template_usage(metrics, template_path, expected_count) -> None:
    """Helper to verify template usage in metrics."""
    template_usage = metrics.template_usage.get(template_path)
    if template_usage is None:
        pytest.fail(f"Expected usage count for template '{template_path}', got None")
    if template_usage != expected_count:
        pytest.fail(
            f"Expected {expected_count} usages for template '{template_path}', got {template_usage}",
        )
    if template_path not in metrics.template_usage:
        pytest.fail(f"Expected '{template_path}' in template usage")


def assert_template_in_adoption(adoption, expected_path) -> None:
    """Helper to verify a template path exists in adoption templates."""
    if adoption is None:
        pytest.fail("Adoption is None")
    template_paths = [t.path for t in adoption.templates]
    if expected_path not in template_paths:
        pytest.fail(f"Expected template path '{expected_path}' not found in {template_paths}")


@pytest.mark.asyncio
async def test_collect_pipeline_metrics(
    initialized_tracker: TemplateAdoptionTracker,
    template_factory,
    pipeline_factory,
) -> None:
    """Test metrics collection for a single pipeline using fixtures."""
    # Create test templates using the factory
    template1 = template_factory(name="template1.yaml", path="templates/steps/template1.yaml")
    template2 = template_factory(name="template2.yaml", path="templates/jobs/template2.yaml")

    # Create a pipeline with these templates
    pipeline = pipeline_factory(
        templates=[template1, template2],
        usage_type=UsageType.INCLUDE,
    )

    # Collect metrics
    metrics = initialized_tracker._collect_pipeline_metrics(pipeline)

    # Use assert helpers to verify metrics
    if len(metrics.template_usage) != 2:
        pytest.fail(f"Expected 2 template usages, got {len(metrics.template_usage)}")

    # Check template usage using helper
    assert_template_usage(metrics, "templates/steps/template1.yaml", 1)
    assert_template_usage(metrics, "templates/jobs/template2.yaml", 1)

    # Verify target and compliance mode are set correctly
    if metrics.target is not initialized_tracker.target:
        pytest.fail("Expected target to be set in metrics")
    if metrics.compliance_mode is not initialized_tracker.compliance_mode:
        pytest.fail("Expected compliance_mode to be set in metrics")


@pytest.mark.asyncio
async def test_collect_repository_metrics(
    initialized_tracker: TemplateAdoptionTracker,
    template_factory,
    pipeline_factory,
    repository_factory,
) -> None:
    """Test metrics collection for a repository."""
    # Create test templates using the factory
    template1 = template_factory(name="template1.yaml", path="templates/steps/template1.yaml")
    template2 = template_factory(name="template2.yaml", path="templates/jobs/template2.yaml")
    template3 = template_factory(name="template3.yaml", path="templates/stages/template3.yaml")

    # Create pipelines with these templates
    include_pipeline = pipeline_factory(
        pid=101,
        name="include-pipeline.yml",
        templates=[template1, template2, template3],
        usage_type=UsageType.INCLUDE,
    )

    extend_pipeline = pipeline_factory(
        pid=102,
        name="extend-pipeline.yml",
        templates=[template3],
        usage_type=UsageType.EXTEND,
    )

    # Create repository with these compliant pipelines
    repo = repository_factory(
        rid="test-repo-1",
        name="test-repository",
        compliant_pipelines=[include_pipeline, extend_pipeline],
        total_no_pipelines=2,
    )

    # Collect metrics
    metrics = initialized_tracker._collect_repository_metrics(repo)

    # Verify metrics content
    if len(metrics.template_usage) != 3:
        pytest.fail(f"Expected 3 template usages, got {len(metrics.template_usage)}")

    # Check template usage using helper
    assert_template_usage(metrics, "templates/steps/template1.yaml", 1)
    assert_template_usage(metrics, "templates/jobs/template2.yaml", 1)
    assert_template_usage(metrics, "templates/stages/template3.yaml", 2)

    # Check pipeline count
    pipeline_count = metrics.get_template_pipeline_count("templates/steps/template1.yaml")
    if pipeline_count != 1:
        pytest.fail(f"Expected 1 pipeline using template1, got {pipeline_count}")
    pipeline_count = metrics.get_template_pipeline_count("templates/jobs/template2.yaml")
    if pipeline_count != 1:
        pytest.fail(f"Expected 1 pipeline using template2, got {pipeline_count}")
    pipeline_count = metrics.get_template_pipeline_count("templates/stages/template3.yaml")
    if pipeline_count != 2:
        pytest.fail(f"Expected 2 pipelines using template3, got {pipeline_count}")

    # Verify target and compliance mode are set correctly
    if metrics.target is not initialized_tracker.target:
        pytest.fail("Expected target to be set in metrics")
    if metrics.compliance_mode is not initialized_tracker.compliance_mode:
        pytest.fail("Expected compliance_mode to be set in metrics")


@pytest.mark.asyncio
async def test_collect_project_metrics(
    initialized_tracker: TemplateAdoptionTracker,
    template_factory,
    pipeline_factory,
    repository_factory,
) -> None:
    """Test metrics collection for a project using factory fixtures."""
    # Create test templates using the factory
    template1 = template_factory(name="template1.yaml", path="templates/steps/template1.yaml")
    template2 = template_factory(name="template2.yaml", path="templates/jobs/template2.yaml")

    # Create test pipelines with these templates
    pipeline1 = pipeline_factory(
        pid=101,
        name="pipeline1.yml",
        repository_id="repo1",
        project_id="project1",
        templates=[template1],
        usage_type=UsageType.INCLUDE,
    )

    pipeline2 = pipeline_factory(
        pid=102,
        name="pipeline2.yml",
        repository_id="repo2",
        project_id="project1",
        templates=[template2],
        usage_type=UsageType.EXTEND,
    )

    # Create repositories
    repo1 = repository_factory(
        rid="repo1",
        name="repo-one",
        project_id="project1",
    )

    repo2 = repository_factory(
        rid="repo2",
        name="repo-two",
        project_id="project1",
    )

    # Create project with compliant pipelines
    project = Project(
        id="project1",
        name="test-project",
    )
    project.compliant_pipelines = [pipeline1, pipeline2]

    # Set up repositories dictionary in tracker
    initialized_tracker._repositories_dict = {
        "repo1": repo1,
        "repo2": repo2,
    }

    # Collect metrics
    metrics = initialized_tracker._collect_project_metrics(project)

    # Verify metrics content
    if len(metrics.template_usage) != 2:
        pytest.fail(f"Expected 2 template usages, got {len(metrics.template_usage)}")

    # Check template usage using helper
    assert_template_usage(metrics, "templates/steps/template1.yaml", 1)
    assert_template_usage(metrics, "templates/jobs/template2.yaml", 1)

    # Check pipeline count
    pipeline_count = metrics.get_template_pipeline_count("templates/steps/template1.yaml")
    if pipeline_count != 1:
        pytest.fail(f"Expected 1 pipeline using template1, got {pipeline_count}")
    pipeline_count = metrics.get_template_pipeline_count("templates/jobs/template2.yaml")
    if pipeline_count != 1:
        pytest.fail(f"Expected 1 pipeline using template2, got {pipeline_count}")

    # Check repository count
    repo_count = metrics.get_template_repository_count("templates/steps/template1.yaml")
    if repo_count != 1:
        pytest.fail(f"Expected 1 repository using template1, got {repo_count}")
    repo_count = metrics.get_template_repository_count("templates/jobs/template2.yaml")
    if repo_count != 1:
        pytest.fail(f"Expected 1 repository using template2, got {repo_count}")

    # Verify target and compliance mode are set correctly
    if metrics.target is not initialized_tracker.target:
        pytest.fail("Expected target to be set in metrics")
    if metrics.compliance_mode is not initialized_tracker.compliance_mode:
        pytest.fail("Expected compliance_mode to be set in metrics")


@pytest.mark.asyncio
async def test_collect_organization_metrics(
    initialized_tracker: TemplateAdoptionTracker,
    template_factory,
    pipeline_factory,
    repository_factory,
) -> None:
    """Test metrics collection for an organization."""
    # Create test templates using the factory
    template1 = template_factory(name="template1.yaml", path="templates/steps/template1.yaml")
    template2 = template_factory(name="template2.yaml", path="templates/jobs/template2.yaml")

    # Create test pipelines with these templates
    pipeline1 = pipeline_factory(
        pid=101,
        name="pipeline1.yml",
        repository_id="repo1",
        project_id="project1",
        templates=[template1],
        usage_type=UsageType.INCLUDE,
    )

    pipeline2 = pipeline_factory(
        pid=102,
        name="pipeline2.yml",
        repository_id="repo2",
        project_id="project1",
        templates=[template2],
        usage_type=UsageType.EXTEND,
    )

    # Create repositories
    repo1 = repository_factory(
        rid="repo1",
        name="repo-one",
        project_id="project1",
    )

    repo2 = repository_factory(
        rid="repo2",
        name="repo-two",
        project_id="project1",
    )

    # Create projects
    project1 = Project(
        id="project1",
        name="project-one",
    )

    project2 = Project(
        id="project2",
        name="project-two",
    )

    # Create organization with compliant pipelines
    organization = Organization(name="TestOrg")
    organization.compliant_pipelines = [pipeline1, pipeline2]

    # Set up dictionaries in tracker
    initialized_tracker._repositories_dict = {
        "repo1": repo1,
        "repo2": repo2,
    }

    initialized_tracker._projects_dict = {
        "project1": project1,
        "project2": project2,
    }

    # Collect metrics
    metrics = initialized_tracker._collect_organization_metrics(organization)

    # Verify metrics content
    if len(metrics.template_usage) != 2:
        pytest.fail(f"Expected 2 template usages, got {len(metrics.template_usage)}")

    # Check template usage using helper
    assert_template_usage(metrics, "templates/steps/template1.yaml", 1)
    assert_template_usage(metrics, "templates/jobs/template2.yaml", 1)

    # Check pipeline count
    pipeline_count = metrics.get_template_pipeline_count("templates/steps/template1.yaml")
    if pipeline_count != 1:
        pytest.fail(f"Expected 1 pipeline using template1, got {pipeline_count}")
    pipeline_count = metrics.get_template_pipeline_count("templates/jobs/template2.yaml")
    if pipeline_count != 1:
        pytest.fail(f"Expected 1 pipeline using template2, got {pipeline_count}")

    # Check repository count
    repo_count = metrics.get_template_repository_count("templates/steps/template1.yaml")
    if repo_count != 1:
        pytest.fail(f"Expected 1 repository using template1, got {repo_count}")
    repo_count = metrics.get_template_repository_count("templates/jobs/template2.yaml")
    if repo_count != 1:
        pytest.fail(f"Expected 1 repository using template2, got {repo_count}")

    # Check project count
    project_count = metrics.get_template_project_count("templates/steps/template1.yaml")
    if project_count != 1:
        pytest.fail(f"Expected 1 project using template1, got {project_count}")
    project_count = metrics.get_template_project_count("templates/jobs/template2.yaml")
    if project_count != 1:
        pytest.fail(f"Expected 1 project using template2, got {project_count}")

    # Verify target and compliance mode are set correctly
    if metrics.target is not initialized_tracker.target:
        pytest.fail("Expected target to be set in metrics")
    if metrics.compliance_mode is not initialized_tracker.compliance_mode:
        pytest.fail("Expected compliance_mode to be set in metrics")


@pytest.mark.asyncio
async def test_get_source_repository_default_branch(
    initialized_tracker: TemplateAdoptionTracker,
    mock_client: Mock,
) -> None:
    """Test retrieval of source repository default branch."""
    # Mock API response from client
    mock_client._get.return_value = {"defaultBranch": "refs/heads/develop"}

    # Call method
    result = initialized_tracker._get_source_repository_default_branch()

    # Verify results
    if result != "develop":
        pytest.fail(f"Expected default branch 'develop', got '{result}'")

    # Verify API call
    expected_url = f"{mock_client.base_url}/{initialized_tracker.source.project}/_apis/git/repositories/{initialized_tracker.source.repository}"  # noqa: E501
    mock_client._get.assert_called_once_with(expected_url)

    # Test with different branch
    mock_client._get.reset_mock()
    mock_client._get.return_value = {"defaultBranch": "refs/heads/main"}

    result = initialized_tracker._get_source_repository_default_branch()
    if result != "main":
        pytest.fail(f"Expected default branch 'main', got '{result}'")


### Miscellaneous Tests ###
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_compliant"),
    [
        (ComplianceMode.ANY, True),
        (ComplianceMode.MAJORITY, True),
        (ComplianceMode.ALL, False),
    ],
)
async def test_compliance_modes_parameterized(
    initialized_tracker: TemplateAdoptionTracker,
    mode: ComplianceMode,
    expected_compliant: bool,  # noqa: FBT001
) -> None:
    """Test that different compliance modes affect compliance determination."""
    # Set up repository with 50% compliance (2 out of 4 pipelines)
    repo = Repository(
        id="test-repo",
        name="test-repo",
        default_branch="main",
        project_id="project1",
        total_no_pipelines=4,
    )
    repo.compliant_pipelines = initialized_tracker._all_pipelines[:2]  # First two are compliant

    # Test compliance with the specified mode
    is_compliant = repo.is_compliant(mode)
    if is_compliant != expected_compliant:
        pytest.fail(f"Repository compliance with {mode.name} mode should be {expected_compliant}, got {is_compliant}")


@pytest.mark.asyncio
async def test_concurrent_repository_processing(
    initialized_tracker: TemplateAdoptionTracker,
    mock_client: Mock,
) -> None:
    """Test concurrent repository processing respects MAX_CONCURRENT_PROCESSING."""
    # Create more repositories than MAX_CONCURRENT_PROCESSING
    repositories = [
        Repository(
            id=f"repo{i}",
            name=f"test-repo-{i}",
            default_branch="main",
        )
        for i in range(15)  # More than MAX_CONCURRENT_PROCESSING
    ]

    mock_client.list_repositories_async.return_value = repositories
    mock_client.get_project_async.return_value = Project(
        id="project1",
        name="Test-Project",
    )

    # Run tracking
    await initialized_tracker.track()

    # Verify concurrent processing
    if initialized_tracker.MAX_CONCURRENT_PROCESSING != 10:
        pytest.fail(f"Expected MAX_CONCURRENT_PROCESSING to be 10, got {initialized_tracker.MAX_CONCURRENT_PROCESSING}")


@pytest.mark.asyncio
async def test_template_branch_mismatch_warning(
    initialized_tracker: TemplateAdoptionTracker,
    caplog,  # pytest fixture for capturing logs
) -> None:
    """Test warning when template branch doesn't match source."""
    pipeline_content = """
    resources:
      repositories:
        - repository: templates
          type: git
          name: Pipeline-Library/pipeline-templates
          ref: refs/heads/develop  # Different from source branch

    extends:
      template: templates/stages/dotnet-ci.yaml@templates
    """

    pipeline = Pipeline(
        id=1,
        name="branch-mismatch.yml",
        folder="src",
        path="src/branch-mismatch.yml",
        content=pipeline_content,
        repository_id="repo1",
    )

    # Process pipeline
    with caplog.at_level(logging.WARNING):
        processed = await initialized_tracker._process_pipeline(pipeline)

    # Verify warning was logged
    if "uses different branch" not in caplog.text:
        pytest.fail("Expected branch mismatch warning")

    # Verify pipeline was not marked as compliant
    if processed.adoption is not None:
        pytest.fail("Expected pipeline to be non-compliant due to branch mismatch")


@pytest.mark.asyncio
async def test_async_context_manager(mock_client: Mock) -> None:
    """Test async context manager functionality."""
    # Mock async context manager methods
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async with TemplateAdoptionTracker(
        client=mock_client,
        target=AdoptionTarget(organization="TestOrg", project="Test-Project"),
        source=TemplateSource(
            project="Pipeline-Library",
            repository="pipeline-templates",
            branch="main",
        ),
    ) as tracker:
        if not isinstance(tracker, TemplateAdoptionTracker):
            pytest.fail("Expected TemplateAdoptionTracker instance")

        # Verify context manager setup
        mock_client.__aenter__.assert_called_once()

    # Verify context manager cleanup
    mock_client.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_yaml_parsing_error_handling(
    initialized_tracker: TemplateAdoptionTracker,
) -> None:
    """Test handling of invalid YAML content."""
    invalid_yaml = """
    invalid:
      - yaml:
          content: [
    """

    pipeline = Pipeline(
        id=1,
        name="invalid.yml",
        folder="src",
        path="src/invalid.yml",
        content=invalid_yaml,
        repository_id="repo1",
    )

    # Should handle YAML errors gracefully
    processed = await initialized_tracker._process_pipeline(pipeline)
    if processed.adoption is not None:
        pytest.fail("Expected None adoption for invalid YAML")


@pytest.mark.asyncio
async def test_empty_repository_compliance() -> None:
    """Test compliance calculation for repositories with no pipelines."""
    # Set up empty repository
    repo = Repository(
        id="empty-repo",
        name="empty-repo",
        default_branch="main",
        project_id="project1",
        total_no_pipelines=0,
    )
    repo.compliant_pipelines = []

    # Check compliance in different modes
    if repo.is_compliant(ComplianceMode.ALL):
        pytest.fail("Empty repository should not be compliant in ALL mode")

    if repo.is_compliant(ComplianceMode.MAJORITY):
        pytest.fail("Empty repository should not be compliant in MAJORITY mode")

    if repo.is_compliant(ComplianceMode.ANY):
        pytest.fail("Empty repository should not be compliant in ANY mode")
