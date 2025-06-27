# ruff: noqa: SLF001,PLR2004
import logging
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.models import TemplateSource
from ado_template_tracker.utils.scanner import RepositoryScanner


@pytest.fixture
def mock_client() -> Mock:
    """Create a mock Azure DevOps client."""
    client = Mock(spec=AzureDevOpsClient)
    client.base_url = "https://dev.azure.com/test-org"
    return client


@pytest_asyncio.fixture
async def scanner(mock_client: Mock) -> RepositoryScanner:
    """Create a RepositoryScanner instance with mock client."""
    return RepositoryScanner(mock_client)


@pytest.fixture
def template_source() -> TemplateSource:
    """Create a template source configuration."""
    return TemplateSource(
        project="test-project",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def mock_yaml_items() -> list[dict]:
    """Create sample YAML file items from repository."""
    return [
        {
            "path": "/templates/steps/build.yaml",
            "isFolder": False,
            "contentMetadata": {"fileName": "build.yaml"},
        },
        {
            "path": "/templates/jobs/test.yml",
            "isFolder": False,
            "contentMetadata": {"fileName": "test.yml"},
        },
        {
            "path": "/templates",
            "isFolder": True,
            "contentMetadata": {"fileName": "templates"},
        },
        {
            "path": "/docs/readme.md",
            "isFolder": False,
            "contentMetadata": {"fileName": "readme.md"},
        },
    ]


@pytest.mark.asyncio
async def test_initialization(mock_client: Mock) -> None:
    """Test scanner initialization."""
    scanner = RepositoryScanner(mock_client)
    if scanner.client != mock_client:
        pytest.fail("Client reference not properly set in Scanner")


@pytest.mark.asyncio
async def test_scan_entire_repository(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_yaml_items: list[dict],
) -> None:
    """Test scanning entire repository for YAML files."""
    # Setup mocks
    scanner._get_repository_items = AsyncMock(return_value=mock_yaml_items)
    scanner._process_yaml_files = AsyncMock(
        return_value=[
            ("/templates/steps/build.yaml", "steps:\n  - script: echo 'Building'"),
            ("/templates/jobs/test.yml", "jobs:\n  - job: Test\n    steps:\n      - script: echo 'Testing'"),
        ],
    )

    # Call the method under test
    result = await scanner._scan_entire_repository(template_source)

    # Verify the correct methods were called
    scanner._get_repository_items.assert_awaited_once_with(
        source=template_source,
        recursion_level="full",
        scope_path=None,
    )
    scanner._process_yaml_files.assert_awaited_once_with(mock_yaml_items, template_source)

    # Verify the result
    if len(result) != 2:
        pytest.fail(f"Expected 2 YAML files, got {len(result)}")
    if result[0][0] != "/templates/steps/build.yaml":
        pytest.fail(f"Unexpected file path: {result[0][0]}")
    if "Building" not in result[0][1]:
        pytest.fail(f"Unexpected file content: {result[0][1]}")


@pytest.mark.asyncio
async def test_scan_directories(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_yaml_items: list[dict],
) -> None:
    """Test scanning specific directories for YAML files."""
    # Setup source with directories
    template_source.directories = ["/templates/steps", "/templates/jobs"]

    # Setup mocks
    scanner._get_repository_items = AsyncMock(return_value=mock_yaml_items)
    scanner._process_yaml_files = AsyncMock(
        return_value=[
            ("/templates/steps/build.yaml", "steps:\n  - script: echo 'Building'"),
        ],
    )

    # Call the method under test
    result = await scanner._scan_directories(template_source)

    # Verify the correct methods were called with proper arguments
    get_items_no_calls = scanner._get_repository_items.await_count
    if get_items_no_calls != 2:
        pytest.fail(f"Expected 2 calls to get_repository_items, got {get_items_no_calls}")
    scanner._get_repository_items.assert_any_await(
        source=template_source,
        recursion_level="full",
        scope_path="templates/steps",
    )
    scanner._get_repository_items.assert_any_await(
        source=template_source,
        recursion_level="full",
        scope_path="templates/jobs",
    )

    # Verify the result
    if len(result) != 2:  # Each directory call returns one file
        pytest.fail(f"Expected 2 total YAML files from both directories, got {len(result)}")


@pytest.mark.asyncio
async def test_scan_method_delegates_properly(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
) -> None:
    """Test that scan method delegates to appropriate methods based on directories."""
    # Setup mocks
    scanner._scan_entire_repository = AsyncMock(return_value=[("file1.yaml", "content1")])
    scanner._scan_directories = AsyncMock(return_value=[("file2.yaml", "content2")])

    # Test with no directories (should scan entire repo)
    template_source.directories = []
    await scanner.scan(template_source)
    scanner._scan_entire_repository.assert_awaited_once_with(template_source)
    scanner._scan_directories.assert_not_awaited()

    # Reset mocks
    scanner._scan_entire_repository.reset_mock()
    scanner._scan_directories.reset_mock()

    # Test with root directory (should scan entire repo)
    template_source.directories = ["/"]
    await scanner.scan(template_source)
    scanner._scan_entire_repository.assert_awaited_once_with(template_source)
    scanner._scan_directories.assert_not_awaited()

    # Reset mocks
    scanner._scan_entire_repository.reset_mock()
    scanner._scan_directories.reset_mock()

    # Test with specific directories (should scan directories)
    template_source.directories = ["/templates"]
    await scanner.scan(template_source)
    scanner._scan_entire_repository.assert_not_awaited()
    scanner._scan_directories.assert_awaited_once_with(template_source)


@pytest.mark.asyncio
async def test_get_repository_items(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_client: Mock,
    mock_yaml_items: list[dict],
) -> None:
    """Test retrieving repository items from API."""
    # Setup mock client response
    mock_client._get_async = AsyncMock(return_value={"value": mock_yaml_items})

    # Call the method under test
    result = await scanner._get_repository_items(
        source=template_source,
        recursion_level="full",
    )

    # Verify API call
    expected_url = (
        f"{mock_client.base_url}/{template_source.project}/_apis/git/repositories/{template_source.repository}/items"
    )
    expected_params = {
        "recursionLevel": "full",
        "version": "main",
        "versionType": "branch",
    }
    mock_client._get_async.assert_awaited_once_with(url=expected_url, params=expected_params)

    # Verify result
    if result != mock_yaml_items:
        pytest.fail("Repository items not returned correctly")


@pytest.mark.asyncio
async def test_get_repository_items_with_scope_path(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_client: Mock,
    mock_yaml_items: list[dict],
) -> None:
    """Test retrieving repository items with a scope path."""
    # Setup mock client response
    mock_client._get_async = AsyncMock(return_value={"value": mock_yaml_items})

    # Call the method under test
    result = await scanner._get_repository_items(
        source=template_source,
        recursion_level="full",
        scope_path="templates",
    )

    # Verify API call includes scope path
    expected_params = {
        "recursionLevel": "full",
        "version": "main",
        "versionType": "branch",
        "scopePath": "templates",
    }
    _, kwargs = mock_client._get_async.call_args
    if kwargs["params"] != expected_params:
        pytest.fail(f"Expected params {expected_params}, got {kwargs['params']}")

    # Verify result
    if result != mock_yaml_items:
        pytest.fail("Repository items not returned correctly")


@pytest.mark.asyncio
async def test_get_repository_items_error_handling(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_client: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when retrieving repository items."""
    # Setup mock client to raise exception
    mock_client._get_async = AsyncMock(side_effect=Exception("API error"))

    # Call the method under test with logging captured
    with caplog.at_level(logging.ERROR):
        result = await scanner._get_repository_items(
            source=template_source,
            recursion_level="full",
        )

    # Verify empty result on error
    if result != []:
        pytest.fail("Expected empty list on error")

    # Verify error was logged
    if "failed to get repository items" not in caplog.text:
        pytest.fail("Error not properly logged")


@pytest.mark.asyncio
async def test_process_yaml_files(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_client: Mock,
    mock_yaml_items: list[dict],
) -> None:
    """Test processing repository items to extract YAML files."""
    # Setup mock client response for file content
    mock_client._get_file_content_async = AsyncMock(
        side_effect=[
            "steps:\n  - script: echo 'Building'",
            "jobs:\n  - job: Test\n    steps:\n      - script: echo 'Testing'",
        ],
    )

    # Call the method under test
    result = await scanner._process_yaml_files(mock_yaml_items, template_source)

    # Verify file content was retrieved correctly
    get_file_calls = mock_client._get_file_content_async.await_count
    if get_file_calls != 2:
        pytest.fail(f"Expected 2 calls to get_file_content_async, got {get_file_calls}")

    # Should only process the YAML files
    mock_client._get_file_content_async.assert_any_await(
        template_source.project,
        template_source.repository,
        "templates/steps/build.yaml",
        template_source.branch,
    )
    mock_client._get_file_content_async.assert_any_await(
        template_source.project,
        template_source.repository,
        "templates/jobs/test.yml",
        template_source.branch,
    )

    # Verify result format
    if len(result) != 2:
        pytest.fail(f"Expected 2 YAML files, got {len(result)}")

    # Verify file paths
    file_paths = [item[0] for item in result]
    if "templates/steps/build.yaml" not in file_paths or "templates/jobs/test.yml" not in file_paths:
        pytest.fail(f"Expected YAML file paths not found in results: {file_paths}")

    # Verify content
    if "Building" not in result[0][1] and "Building" not in result[1][1]:
        pytest.fail("Expected content not found in results")


@pytest.mark.asyncio
async def test_process_yaml_files_error_handling(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_client: Mock,
    mock_yaml_items: list[dict],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when processing YAML files."""
    # Setup mock client to raise exception for one file
    mock_client._get_file_content_async = AsyncMock(
        side_effect=[
            Exception("Cannot retrieve file"),
            "jobs:\n  - job: Test\n    steps:\n      - script: echo 'Testing'",
        ],
    )

    # Call the method under test with logging captured
    with caplog.at_level(logging.ERROR):
        result = await scanner._process_yaml_files(mock_yaml_items, template_source)

    # Verify only successful file is included in result
    if len(result) != 1:
        pytest.fail(f"Expected 1 successful YAML file, got {len(result)}")

    # Verify error was logged
    if "failed to get content for" not in caplog.text:
        pytest.fail("Error not properly logged")


@pytest.mark.asyncio
async def test_integration_scan_flow(
    scanner: RepositoryScanner,
    template_source: TemplateSource,
    mock_client: Mock,
    mock_yaml_items: list[dict],
) -> None:
    """Test the full scan workflow integration."""
    # Setup source with directories
    template_source.directories = ["/templates"]

    # Setup mock client responses
    mock_client._get_async = AsyncMock(return_value={"value": mock_yaml_items})
    mock_client._get_file_content_async = AsyncMock(
        side_effect=[
            "steps:\n  - script: echo 'Building'",
            "jobs:\n  - job: Test\n    steps:\n      - script: echo 'Testing'",
        ],
    )

    # Call the main scan method
    result = await scanner.scan(template_source)

    # Verify results
    if len(result) != 2:
        pytest.fail(f"Expected 2 YAML files, got {len(result)}")

    # Check file paths and content
    paths = [path for path, _ in result]
    if "templates/steps/build.yaml" not in paths or "templates/jobs/test.yml" not in paths:
        pytest.fail(f"Expected paths not in result: {paths}")
