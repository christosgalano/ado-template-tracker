# ruff: noqa: SLF001,PLR2004,S105
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
import requests

from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.exceptions import AuthenticationError, SchemaFetchError


def test_initialization_with_token() -> None:
    """Test client initialization with explicit token."""
    # Test with explicit token
    client = AzureDevOpsClient("test-org", "test-token")
    if client.organization != "test-org":
        pytest.fail("Expected organization to be 'test-org'")
    if client.token != "test-token":
        pytest.fail("Expected token to be 'test-token'")
    if client.base_url != "https://dev.azure.com/test-org":
        pytest.fail(f"Expected base_url to be 'https://dev.azure.com/test-org', got '{client.base_url}'")


def test_initialization_with_azure_credential() -> None:
    """Test client initialization with Azure credential."""
    with patch.object(AzureDevOpsClient, "get_access_token") as mock_get_token:
        mock_get_token.return_value = "azure-token"

        # Test with token from Azure credential
        client = AzureDevOpsClient("test-org")

        # Verify get_access_token was called
        mock_get_token.assert_called_once()

        if client.token != "azure-token":
            pytest.fail(f"Expected token to be 'azure-token', got '{client.token}'")


def test_get_access_token_success() -> None:
    """Test successful token retrieval from DefaultAzureCredential."""
    with patch("ado_template_tracker.core.client.DefaultAzureCredential") as mock_credential:
        # Setup the mock token response
        mock_token = mock_credential.return_value.get_token.return_value
        mock_token.token = "mock-azure-token"

        client = AzureDevOpsClient("test-org", "test-token")  # Token will be ignored in this test
        token = client.get_access_token()

        # Verify the correct resource ID was used
        mock_credential.return_value.get_token.assert_called_once_with(AzureDevOpsClient.AZURE_DEVOPS_RESOURCE_ID)

        if token != "mock-azure-token":
            pytest.fail(f"Expected token 'mock-azure-token', got '{token}'")


def test_get_access_token_request_exception() -> None:
    """Test token retrieval failure due to request exception."""
    with patch("ado_template_tracker.core.client.DefaultAzureCredential") as mock_credential:
        mock_credential.return_value.get_token.side_effect = requests.exceptions.RequestException("Network error")

        client = AzureDevOpsClient("test-org", "test-token")  # Will use this token instead
        token = client.get_access_token()

        if token is not None:
            pytest.fail(f"Expected None on exception, got '{token}'")


def test_get_access_token_general_exception() -> None:
    """Test token retrieval failure due to general exception."""
    with patch("ado_template_tracker.core.client.DefaultAzureCredential") as mock_credential:
        mock_credential.return_value.get_token.side_effect = Exception("Unknown error")

        client = AzureDevOpsClient("test-org", "test-token")  # Will use this token instead
        token = client.get_access_token()

        if token is not None:
            pytest.fail(f"Expected None on exception, got '{token}'")


def test_authentication_error_on_empty_token() -> None:
    """Test that authentication error is raised when no token is available."""
    with patch.object(AzureDevOpsClient, "get_access_token") as mock_get_token:
        mock_get_token.return_value = None

        with pytest.raises(AuthenticationError):
            AzureDevOpsClient("test-org")


def test_retry_if_status_code() -> None:
    """Test the retry condition for HTTP status codes."""
    # Create test errors with various status codes
    retryable_error = aiohttp.ClientResponseError(request_info=None, history=(), status=503)

    non_retryable_error = aiohttp.ClientResponseError(request_info=None, history=(), status=404)

    different_error = ValueError("Not a ClientResponseError")

    # Test the retry condition
    if not AzureDevOpsClient._retry_if_status_code(retryable_error):
        pytest.fail("Expected retry for status code 503")

    if AzureDevOpsClient._retry_if_status_code(non_retryable_error):
        pytest.fail("Expected no retry for status code 404")

    if AzureDevOpsClient._retry_if_status_code(different_error):
        pytest.fail("Expected no retry for non-ClientResponseError")


class TestSyncOperations:
    """Test suite for synchronous Azure DevOps client operations."""

    def setup_method(self) -> None:
        """Setup test client."""
        self.client = AzureDevOpsClient("org", "pat")

    def test_context_manager(self) -> None:
        """Test context manager."""
        with self.client as client:
            _ = client.session  # lazy session creation
            if client._sync_session is None:
                pytest.fail("Session not created")

        if client._sync_session is not None:
            pytest.fail("Session not cleaned up")

    def test_error_handling(self) -> None:
        """Test error handling for API responses."""
        with patch.object(self.client, "_get") as mock_get:
            # Test 401 response
            mock_get.side_effect = AuthenticationError()
            with pytest.raises(AuthenticationError):
                self.client.get_project("proj1")

            # Test network error
            mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
            with pytest.raises(requests.exceptions.ConnectionError):
                self.client.get_project("proj1")

    def test_list_projects(self) -> None:
        """Test project listing operation."""
        with patch.object(self.client, "_get") as mock_get:
            mock_get.return_value = {
                "value": [{"id": "proj1", "name": "Project One"}],
            }
            projects = self.client.list_projects()
            if len(projects) != 1:
                pytest.fail("Expected one project")

    def test_get_project(self) -> None:
        """Test project retrieval operation."""
        with patch.object(self.client, "_get") as mock_get:
            mock_get.return_value = {"id": "proj1", "name": "Project One"}
            project = self.client.get_project("proj1")
            if project.name != "Project One":
                pytest.fail("Unexpected project name")

            # Test error case
            mock_get.side_effect = requests.exceptions.RequestException()
            mock_get.return_value = None
            with pytest.raises(requests.exceptions.RequestException):
                self.client.get_project("proj2")

    def test_list_repositories(self) -> None:
        """Test repository listing operation."""
        with patch.object(self.client, "_get") as mock_get:
            mock_get.return_value = {
                "value": [
                    {
                        "id": "repo1",
                        "name": "Repo One",
                        "defaultBranch": "main",
                        "project": {"id": "proj1", "name": "Project One"},
                    },
                ],
            }
            repos = self.client.list_repositories("proj1")
            if len(repos) != 1:
                pytest.fail("Expected one repository")
            if repos[0].name != "Repo One":
                pytest.fail("Unexpected repository name")

            # Test error case
            mock_get.side_effect = requests.exceptions.RequestException()
            mock_get.return_value = None
            with pytest.raises(requests.exceptions.RequestException):
                self.client.list_repositories("proj2")

    def test_get_repository(self) -> None:
        """Test repository retrieval operation."""
        with patch.object(self.client, "_get") as mock_get:
            mock_get.return_value = {
                "id": "repo1",
                "name": "Repo One",
                "defaultBranch": "main",
                "project": {"id": "proj1", "name": "Project One"},
            }
            repo = self.client.get_repository("proj1", "repo1")
            if repo.name != "Repo One":
                pytest.fail("Unexpected repository name")

            # Test error case
            mock_get.side_effect = requests.exceptions.RequestException()
            mock_get.return_value = None
            with pytest.raises(requests.exceptions.RequestException):
                self.client.get_repository("proj1", "repo2")

    def test_list_pipelines(self) -> None:
        """Test pipeline listing operation."""
        with patch.object(self.client, "_get") as mock_get:
            # Mock responses for full pipeline listing workflow
            mock_get.side_effect = [
                # 1. Pipeline IDs response
                {
                    "value": [
                        {"id": 1},
                        {"id": 2},
                    ],
                },
                # 2. First pipeline details
                {
                    "id": 1,
                    "name": "Pipeline One",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                # 3. Repository details for first pipeline
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {
                        "id": "proj1",
                        "name": "Project One",
                    },
                },
                # 4. File content for first pipeline
                {
                    "content": "trigger:\n  - main\n",
                },
                # 5. Second pipeline details
                {
                    "id": 2,
                    "name": "Pipeline Two",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                # 6. Repository details for second pipeline
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {
                        "id": "proj1",
                        "name": "Project One",
                    },
                },
                # 7. File content for second pipeline
                {
                    "content": "trigger:\n  - main\n",
                },
            ]

            pipelines = self.client.list_pipelines("proj1")
            if len(pipelines) != 2:
                pytest.fail("Expected two pipelines")
            if pipelines[0].name != "Pipeline One":
                pytest.fail("Unexpected pipeline name")

            # Test error case
            mock_get.side_effect = requests.exceptions.RequestException()
            with pytest.raises(requests.exceptions.RequestException):
                self.client.list_pipelines("proj2")

    def test_list_pipelines_threaded(self) -> None:
        """Test threaded pipeline listing operation."""
        with patch.object(self.client, "_get") as mock_get:
            mock_get.side_effect = [
                # 1. Pipeline IDs response
                {
                    "value": [{"id": 1}, {"id": 2}],
                },
                # 2. First pipeline details
                {
                    "id": 1,
                    "name": "Pipeline One",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                # 3. Repository details for first pipeline
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {"id": "proj1", "name": "Project One"},
                },
                # 4. File content for first pipeline
                {
                    "content": "trigger:\n  - main\n",
                },
                # 5. Second pipeline details
                {
                    "id": 2,
                    "name": "Pipeline Two",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                # 6. Repository details for second pipeline
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {"id": "proj1", "name": "Project One"},
                },
                # 7. File content for second pipeline
                {
                    "content": "trigger:\n  - main\n",
                },
            ]

            pipelines = self.client.list_pipelines_threaded("proj1", max_workers=2)

            # Verify results
            if len(pipelines) != 2:
                pytest.fail("Expected two pipelines")
            if pipelines[0].name != "Pipeline One":
                pytest.fail("Unexpected pipeline name")
            if pipelines[0].content != "trigger:\n  - main\n":
                pytest.fail("Unexpected pipeline content")

            # Test error case
            mock_get.side_effect = requests.exceptions.RequestException()
            with pytest.raises(requests.exceptions.RequestException):
                self.client.list_pipelines_threaded("proj2", max_workers=2)

    def test_get_pipeline_by_id(self) -> None:
        """Test pipeline retrieval operation."""
        with patch.object(self.client, "_get") as mock_get:
            # Mock pipeline and repository responses
            mock_get.side_effect = [
                {
                    "id": 1,
                    "name": "Pipeline One",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "project": {"id": "proj1", "name": "Project One"},
                },
                {
                    "content": "trigger:\n  - main\n",
                },
            ]

            pipeline = self.client.get_pipeline_by_id("proj1", 1)
            if pipeline.name != "Pipeline One":
                pytest.fail("Unexpected pipeline name")
            if pipeline.content != "trigger:\n  - main\n":
                pytest.fail("Unexpected pipeline content")

            # Test error case
            mock_get.side_effect = requests.exceptions.RequestException()
            with pytest.raises(requests.exceptions.RequestException):
                self.client.get_pipeline_by_id("proj1", 999)

    def test_get_pipeline_schema(self) -> None:
        """Test pipeline schema fetching operation."""
        with patch("requests.get") as mock_get:
            # Test successful schema fetch
            mock_get.return_value.json.return_value = {"$schema": "test-schema"}
            mock_get.return_value.status_code = 200

            schema = self.client.get_pipeline_schema()
            if "$schema" not in schema:
                pytest.fail("Invalid schema response")

            # Test schema fetch error
            mock_get.side_effect = requests.exceptions.RequestException()
            with pytest.raises(SchemaFetchError):
                self.client.get_pipeline_schema()


class TestAsyncOperations:
    """Test suite for asynchronous Azure DevOps client operations."""

    def setup_method(self) -> None:
        """Setup test client."""
        self.client = AzureDevOpsClient("org", "pat")

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test context manager."""
        async with self.client as client:
            if client._async_session is None:
                pytest.fail("Session not created")
        if client._async_session is not None:
            pytest.fail("Session not cleaned up")

    @pytest.mark.asyncio
    async def test_get_async_session_reuse(self) -> None:
        """Test that async session is created once and reused."""
        # First call should create a new session
        session1 = await self.client.get_async_session()

        # Second call should return the same session object
        session2 = await self.client.get_async_session()

        if session1 is not session2:
            pytest.fail("Expected same session to be returned on subsequent calls")

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        """Test async error handling cases."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            # Test authentication error
            mock_get.side_effect = AuthenticationError()
            with pytest.raises(AuthenticationError):
                await self.client.get_project_async("proj1")

            # Test network error
            mock_get.side_effect = aiohttp.ClientConnectionError("Connection failed")
            with pytest.raises(aiohttp.ClientError):
                await self.client.get_project_async("proj1")

            # Test other HTTP errors
            mock_get.side_effect = aiohttp.ClientResponseError(
                request_info=aiohttp.RequestInfo(
                    url="http://test",
                    method="GET",
                    headers={},
                    real_url="http://test",
                ),
                history=(),
                status=500,
                message="Internal Server Error",
            )
            with pytest.raises(aiohttp.ClientResponseError):
                await self.client.get_project_async("proj1")

    @pytest.mark.asyncio
    async def test_list_projects(self) -> None:
        """Test async project listing operation."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "value": [{"id": "proj1", "name": "Project One"}],
            }
            projects = await self.client.list_projects_async()
            if len(projects) != 1:
                pytest.fail("Expected one project")

            # Test error case
            mock_get.side_effect = aiohttp.ClientResponseError(None, None)
            with pytest.raises(aiohttp.ClientResponseError):
                await self.client.list_projects_async()

    @pytest.mark.asyncio
    async def test_get_project(self) -> None:
        """Test async project retrieval operation."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"id": "proj1", "name": "Project One"}
            project = await self.client.get_project_async("proj1")
            if project.name != "Project One":
                pytest.fail("Unexpected project name")

            # Test error case
            mock_get.side_effect = aiohttp.ClientResponseError(None, None)
            with pytest.raises(aiohttp.ClientResponseError):
                await self.client.get_project_async("proj2")

    @pytest.mark.asyncio
    async def test_list_repositories(self) -> None:
        """Test async repository listing operation."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "value": [
                    {
                        "id": "repo1",
                        "name": "Repo One",
                        "defaultBranch": "main",
                        "isDisabled": False,
                        "project": {"id": "proj1", "name": "Project One"},
                    },
                ],
            }
            repos = await self.client.list_repositories_async("proj1")
            if len(repos) != 1:
                pytest.fail("Expected one repository")
            if repos[0].name != "Repo One":
                pytest.fail("Unexpected repository name")

            # Test error case
            mock_get.side_effect = aiohttp.ClientResponseError(None, None)
            with pytest.raises(aiohttp.ClientResponseError):
                await self.client.list_repositories_async("proj2")

    @pytest.mark.asyncio
    async def test_get_repository(self) -> None:
        """Test async repository retrieval operation."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "id": "repo1",
                "name": "Repo One",
                "defaultBranch": "main",
                "isDisabled": False,
                "project": {"id": "proj1", "name": "Project One"},
            }
            repo = await self.client.get_repository_async("proj1", "repo1")
            if repo.name != "Repo One":
                pytest.fail("Unexpected repository name")

            # Test error case
            mock_get.side_effect = aiohttp.ClientResponseError(None, None)
            with pytest.raises(aiohttp.ClientResponseError):
                await self.client.get_repository_async("proj1", "repo2")

    @pytest.mark.asyncio
    async def test_list_pipelines(self) -> None:
        """Test async pipeline listing operation."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            # Mock responses for full pipeline listing workflow
            mock_get.side_effect = [
                # 1. Pipeline IDs response
                {
                    "value": [
                        {"id": 1},
                        {"id": 2},
                    ],
                },
                # 2. First pipeline details
                {
                    "id": 1,
                    "name": "Pipeline One",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                # 3. Repository details for first pipeline
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {
                        "id": "proj1",
                        "name": "Project One",
                    },
                },
                # 4. File content for first pipeline
                {
                    "content": "trigger:\n  - main\n",
                },
                # 5. Second pipeline details
                {
                    "id": 2,
                    "name": "Pipeline Two",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                # 6. Repository details for second pipeline
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {
                        "id": "proj1",
                        "name": "Project One",
                    },
                },
                # 7. File content for second pipeline
                {
                    "content": "trigger:\n  - main\n",
                },
            ]

            pipelines = await self.client.list_pipelines_async("proj1")
            if len(pipelines) != 2:
                pytest.fail("Expected two pipelines")
            if pipelines[0].name != "Pipeline One":
                pytest.fail("Unexpected pipeline name")

            # Test error case
            mock_get.side_effect = aiohttp.ClientResponseError(None, None)
            with pytest.raises(aiohttp.ClientResponseError):
                await self.client.list_pipelines_async("proj2")

    @pytest.mark.asyncio
    async def test_get_pipeline_by_id(self) -> None:
        """Test async pipeline retrieval operation."""
        with patch.object(self.client, "_get_async", new_callable=AsyncMock) as mock_get:
            # Mock pipeline and repository responses
            mock_get.side_effect = [
                {
                    "id": 1,
                    "name": "Pipeline One",
                    "folder": "/",
                    "revision": 1,
                    "configuration": {
                        "path": "azure-pipelines.yml",
                        "repository": {"id": "repo1"},
                    },
                },
                {
                    "id": "repo1",
                    "name": "Repo One",
                    "defaultBranch": "main",
                    "isDisabled": False,
                    "project": {"id": "proj1", "name": "Project One"},
                },
                {
                    "content": "trigger:\n  - main\n",
                },
            ]

            pipeline = await self.client.get_pipeline_by_id_async("proj1", 1)
            if pipeline.name != "Pipeline One":
                pytest.fail("Unexpected pipeline name")
            if pipeline.content != "trigger:\n  - main\n":
                pytest.fail("Unexpected pipeline content")

            # Test error case
            mock_get.side_effect = aiohttp.ClientResponseError(None, None)
            with pytest.raises(aiohttp.ClientError):
                await self.client.get_pipeline_by_id_async("proj1", 999)
