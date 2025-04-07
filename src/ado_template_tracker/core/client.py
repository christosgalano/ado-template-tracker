"""Core Azure DevOps API client functionality.

This module provides the main client functionality for interacting with Azure DevOps APIs.
It handles authentication, request management, and data retrieval while providing
both synchronous and asynchronous operation modes.

Key Components:
    AzureDevOpsClient: Main class that orchestrates API interactions
        with retry logic, rate limiting, and connection pooling.

Features:
    - Automatic authentication with DefaultAzureCredential or PAT
    - Synchronous and asynchronous API operations
    - Connection pooling and session management
    - Automatic retry with exponential backoff
    - Rate limiting for batch operations
    - Pipeline content retrieval from repositories
    - Threaded and async batch processing

Dependencies:
    - models.py: Data models for projects, repositories, and pipelines
    - exceptions.py: Custom exceptions for error handling
    - aiohttp: For asynchronous HTTP operations
    - requests: For synchronous HTTP operations
    - azure.identity: For Azure authentication

Example:
    ```python
    from ado_template_tracker.core.client import AzureDevOpsClient
    from ado_template_tracker.core.models import Pipeline, Project

    async def fetch_data():
        async with AzureDevOpsClient(
            organization="org",
            token="pat"
        ) as client:
            # Get project details
            project = await client.get_project_async("project-name")

            # List all pipelines
            pipelines = await client.list_pipelines_async(project.name)

            # Get specific pipeline with content
            pipeline = await client.get_pipeline_by_id_async(
                project.name,
                pipeline_id=123
            )

            # Use threaded operations for better performance
            all_pipelines = client.list_pipelines_threaded(
                project.name,
                max_workers=20
            )
    ```

Raises:
    AuthenticationError: When authentication fails or token is invalid
    SchemaFetchError: When pipeline schema fetch fails
    aiohttp.ClientError: When async API requests fail
    requests.exceptions.RequestException: When sync API requests fail
"""

import asyncio
import concurrent.futures
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import ClassVar
from urllib.parse import quote

import aiohttp
import requests
import tenacity
from azure.identity import DefaultAzureCredential
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ado_template_tracker.core.exceptions import AuthenticationError, SchemaFetchError
from ado_template_tracker.core.models import Pipeline, Project, Repository


class AzureDevOpsClient:
    """Handles API interactions with Azure DevOps at the organization level."""

    API_VERSION = "7.2-preview.1"  # Azure DevOps API version
    AZURE_DEVOPS_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"  # Azure DevOps resource ID
    MAX_RETRIES = 3  # Maximum number of retries for API requests
    RETRY_BACKOFF = 1  # Exponential backoff factor
    RETRY_STATUS_CODES: ClassVar[list[int]] = [
        500,
        502,
        503,
        504,
        429,
        408,
    ]  # Status codes to retry on
    BATCH_SIZE = 100  # Standard batch size for concurrent operations
    RATE_LIMIT_DELAY = 0.1  # 100ms delay between batches
    ASYNC_TOTAL_TIMEOUT = 30  # Total timeout for async requests
    ASYNC_CONNECT_TIMEOUT = 10  # Connection timeout for async requests
    ASYNC_SOCKET_TIMEOUT = 10  # Socket read timeout for async

    def __init__(
        self,
        organization: str,
        token: str | None = None,
        api_version: str = API_VERSION,
    ) -> None:
        # Base configuration
        self.organization = organization
        self.api_version = api_version
        self.base_url = f"https://dev.azure.com/{organization}"

        # Authentication
        self.token = token or self.get_access_token()
        if not self.token:
            raise AuthenticationError
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.default_params = {"api-version": self.api_version}

        # Sessions
        self._sync_session = None
        self._async_session = None

    ### Session methods
    @property
    def session(self) -> requests.Session:
        """Lazy initialization of sync session."""
        if self._sync_session is None:
            self._sync_session = self._create_session()
        return self._sync_session

    async def get_async_session(self) -> aiohttp.ClientSession:
        """Lazy initialization of async session."""
        if self._async_session is None:
            self._async_session = await self._create_async_session()
        return self._async_session

    def _create_session(self) -> requests.Session:
        """Creates a new requests session with retry logic."""
        session = requests.Session()
        retries = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.RETRY_BACKOFF,
            status_forcelist=self.RETRY_STATUS_CODES,
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.headers.update(self.headers)
        return session

    async def _create_async_session(self) -> aiohttp.ClientSession:
        """Creates a new aiohttp client session."""
        return aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(
                total=self.ASYNC_TOTAL_TIMEOUT,
                connect=self.ASYNC_CONNECT_TIMEOUT,
                sock_read=self.ASYNC_SOCKET_TIMEOUT,
            ),
            raise_for_status=True,
        )

    ### Context manager methods
    def __enter__(self) -> "AzureDevOpsClient":
        """Context manager entry for sync operations."""
        if self._sync_session is None:
            self._sync_session = self._create_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Context manager exit for sync operations."""
        if self._sync_session:
            self._sync_session.close()
            self._sync_session = None

    async def __aenter__(self) -> "AzureDevOpsClient":
        """Async context manager entry."""
        if self._async_session is None:
            self._async_session = await self._create_async_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Async context manager exit."""
        if self._async_session:
            await self._async_session.close()
            self._async_session = None

    ### GET methods
    def _get(self, url: str, params: dict | None = None) -> dict:
        """Handles GET requests with error handling and JSON response."""
        try:
            merged_params = {**self.default_params, **(params or {})}
            response = self.session.get(url, params=merged_params)
            if response.status_code == 401:  # noqa: PLR2004
                raise AuthenticationError
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error("client: [%s] %s - %s", e.response.status_code, e.response.reason, url)  # noqa: LOG015, TRY400
            raise
        except requests.exceptions.RequestException as e:
            logging.error("client: Request error: %s - %s", type(e).__name__, url)  # noqa: LOG015, TRY400
            raise

    @staticmethod
    def _retry_if_status_code(exception: Exception) -> bool:
        """Return True if we should retry (in this case when it's an aiohttp.ClientResponseError with specific status codes), False otherwise."""  # noqa: E501
        return (
            isinstance(exception, aiohttp.ClientResponseError)
            and exception.status in AzureDevOpsClient.RETRY_STATUS_CODES
        )

    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        stop=tenacity.stop_after_attempt(MAX_RETRIES),
        retry=tenacity.retry_if_exception(_retry_if_status_code),
        reraise=True,
    )
    async def _get_async(self, url: str, params: dict | None = None) -> dict:
        """Handles async GET requests with error handling."""
        session = await self.get_async_session()
        try:
            merged_params = {**self.default_params, **(params or {})}
            async with session.get(url, params=merged_params) as response:
                if response.status == 401:  # noqa: PLR2004
                    raise AuthenticationError
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            logging.error("client: [%s] %s - %s", e.status, e.message, e.request_info.real_url)  # noqa: LOG015, TRY400
            raise
        except aiohttp.ClientError as e:
            logging.error("client: aiohttp error: %s - %s", type(e).__name__, url)  # noqa: LOG015, TRY400
            raise

    ### Authentication methods
    def get_access_token(self) -> str | None:
        """
        Retrieves an access token using the DefaultAzureCredential.

        This method attempts to obtain an access token for the specified resource
        using the DefaultAzureCredential, which supports various authentication
        methods including managed identity, environment variables, and more.

        Returns:
          str: The access token if successfully retrieved, otherwise None.

        Raises:
          requests.exceptions.Request: If there is an error while making the request.
          Exception: If there is an error while retrieving the access token,
                 it will be logged and None will be returned.
        """
        try:
            credential = DefaultAzureCredential()
            return credential.get_token(self.AZURE_DEVOPS_RESOURCE_ID).token
        except requests.exceptions.RequestException:
            logging.exception("client: HTTP error occurred while retrieving token")
        except Exception:
            logging.exception("client: unexpected error retrieving access token")
        return None

    ### Schema methods
    def get_pipeline_schema(self) -> dict:
        """Gets the YAML schema for Azure DevOps pipelines from GitHub."""
        url = "https://raw.githubusercontent.com/Microsoft/azure-pipelines-vscode/main/service-schema.json"
        headers = {
            "Accept": "application/json",
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.exception("client: failed to fetch schema from GitHub")
            raise SchemaFetchError from e

    ### Project methods
    def list_projects(self) -> list[Project]:
        """Lists all projects in the organization."""
        url = f"{self.base_url}/_apis/projects"
        data = self._get(url)
        return [Project.from_get_response(item) for item in data.get("value", [])]

    async def list_projects_async(self) -> list[Project]:
        """Lists all projects in the organization asynchronously."""
        url = f"{self.base_url}/_apis/projects"
        data = await self._get_async(url)
        return [Project.from_get_response(item) for item in data.get("value", [])]

    def get_project(self, project: str) -> Project:
        """Gets details of a specific project."""
        url = f"{self.base_url}/_apis/projects/{project}"
        data = self._get(url)
        return Project.from_get_response(data)

    async def get_project_async(self, project: str) -> Project:
        """Gets details of a specific project asynchronously."""
        url = f"{self.base_url}/_apis/projects/{project}"
        data = await self._get_async(url)
        return Project.from_get_response(data)

    ### Repository methods
    ### Repository methods
    def list_repositories(self, project: str) -> list[Repository]:
        """Lists all repositories in a project, skipping ghost ones."""
        url = f"{self.base_url}/{project}/_apis/git/repositories"
        data = self._get(url)
        raw_repos = data.get("value", [])
        repositories = []

        def is_reachable(item) -> Repository | None:
            try:
                self._get(f"{self.base_url}/{project}/_apis/git/repositories/{item['id']}")
                return Repository.from_get_response(item)
            except requests.exceptions.RequestException as e:
                if e.response is not None and e.response.status_code == 404:
                    logging.warning(f"Skipping inaccessible repository '{item['name']}': {e}")
                else:
                    logging.exception(f"Error checking repository '{item['name']}': {e}")
            except Exception as e:
                logging.exception(f"Unexpected error while checking repository '{item['name']}': {e}")
            return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(is_reachable, item) for item in raw_repos]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    repositories.append(result)

        return repositories

    async def list_repositories_async(self, project: str) -> list[Repository]:
        """Lists all repositories in a project asynchronously, skipping ghost ones."""
        url = f"{self.base_url}/{project}/_apis/git/repositories"
        data = await self._get_async(url)
        raw_repos = data.get("value", [])
        semaphore = asyncio.Semaphore(10)  # Limit concurrency

        async def is_reachable(item: dict) -> Repository | None:
            async with semaphore:
                try:
                    await self._get_async(f"{self.base_url}/{project}/_apis/git/repositories/{item['id']}")
                    return Repository.from_get_response(item)
                except aiohttp.ClientResponseError as e:
                    if e.status == 404:
                        logging.warning(f"Skipping inaccessible repository '{item['name']}': {e}")
                    else:
                        logging.exception(f"Error checking repository '{item['name']}': {e}")
                except Exception as e:
                    logging.exception(f"Unexpected error while checking repository '{item['name']}': {e}")
                return None

        results = await asyncio.gather(*[is_reachable(item) for item in raw_repos])
        return [repo for repo in results if repo is not None]

    def get_repository(self, project: str, repository: str) -> Repository:
        """Gets details of a specific repository in a project."""
        url = f"{self.base_url}/{project}/_apis/git/repositories/{repository}"
        data = self._get(url)
        return Repository.from_get_response(data)

    async def get_repository_async(self, project: str, repository: str) -> Repository:
        """Gets details of a specific repository in a project asynchronously."""
        url = f"{self.base_url}/{project}/_apis/git/repositories/{repository}"
        data = await self._get_async(url)
        return Repository.from_get_response(data)

    ### Pipeline methods
    def list_pipelines(self, project: str) -> list[Pipeline]:
        """Lists all pipelines in a project."""
        pipeline_ids = self._get_pipeline_ids(project)
        return self._fetch_pipelines_by_ids(project, pipeline_ids)

    def list_pipelines_threaded(
        self,
        project: str,
        max_workers: int = 10,
    ) -> list[Pipeline]:
        """Lists all pipelines in a project using threaded execution."""
        pipeline_ids = self._get_pipeline_ids(project)
        return self._fetch_pipelines_by_ids_threaded(project, pipeline_ids, max_workers)

    async def list_pipelines_async(self, project: str) -> list[Pipeline]:
        """Lists all pipelines in a project asynchronously."""
        pipeline_ids = await self._get_pipeline_ids_async(project)
        return await self._fetch_pipelines_by_ids_async(project, pipeline_ids)

    def get_pipeline_by_id(self, project: str, pipeline_id: int) -> Pipeline:
        """Gets details of a specific pipeline."""
        url = f"{self.base_url}/{project}/_apis/pipelines/{pipeline_id}"
        data = self._get(url)

        # Get pipeline content if path is available
        content = None
        project_id = None
        if data.get("configuration", {}).get("path"):
            pipeline_name = data["name"]
            repo_id = data["configuration"]["repository"]["id"]
            path = data["configuration"]["path"]

            try:
                repo = self.get_repository(project, repo_id)
                project_id = repo.project_id
                logging.debug(
                    "client: using default branch '%s' for pipeline '%s' in repository '%s'",
                    repo.default_branch,
                    pipeline_name,
                    repo.name,
                )
                content = self._get_file_content(
                    project,
                    repo.id,
                    path,
                    repo.default_branch,
                )
            except requests.exceptions.RequestException:
                logging.exception("client: failed to get pipeline content")
                content = None

        return Pipeline.from_get_response(data, project_id, content)

    async def get_pipeline_by_id_async(
        self,
        project: str,
        pipeline_id: int,
    ) -> Pipeline:
        """Gets details of a specific pipeline asynchronously."""
        url = f"{self.base_url}/{project}/_apis/pipelines/{pipeline_id}"
        data = await self._get_async(url)

        # Get pipeline content if path is available
        content = None
        project_id = None
        if data.get("configuration", {}).get("path"):
            pipeline_name = data["name"]
            repo_id = data["configuration"]["repository"]["id"]
            path = data["configuration"]["path"]

            try:
                repo = await self.get_repository_async(project, repo_id)
                project_id = repo.project_id
                logging.debug(
                    "client: using default branch '%s' for pipeline '%s' in repository '%s'",
                    repo.default_branch,
                    pipeline_name,
                    repo.name,
                )
                content = await self._get_file_content_async(
                    project,
                    repo.id,
                    path,
                    repo.default_branch,
                )
            except aiohttp.ClientError:
                logging.exception("client: failed to get pipeline content")
                content = None

        return Pipeline.from_get_response(data, project_id, content)

    def _fetch_pipelines_by_ids(
        self,
        project: str,
        pipeline_ids: list[int],
    ) -> list[Pipeline]:
        """Fetches multiple pipelines in a project by their ID in batches."""
        results = []
        total_pipelines = len(pipeline_ids)
        batch_count = (total_pipelines + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        for batch_num, i in enumerate(range(0, total_pipelines, self.BATCH_SIZE), 1):
            batch = pipeline_ids[i : i + self.BATCH_SIZE]
            batch_results = [self.get_pipeline_by_id(project, pid) for pid in batch]
            results.extend(batch_results)
            if batch_num < batch_count:
                time.sleep(self.RATE_LIMIT_DELAY)

        return results

    def _fetch_pipelines_by_ids_threaded(
        self,
        project: str,
        pipeline_ids: list[int],
        max_workers: int = 10,
    ) -> list[Pipeline]:
        """Fetches multiple pipelines in a project by their ID using thread pool."""
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pid = {executor.submit(self.get_pipeline_by_id, project, pid): pid for pid in pipeline_ids}

            for future in concurrent.futures.as_completed(future_to_pid):
                pid = future_to_pid[future]
                try:
                    pipeline = future.result()
                    results.append(pipeline)
                except Exception:
                    logging.exception("client: failed to fetch pipeline %s", pid)

        return results

    async def _fetch_pipelines_by_ids_async(
        self,
        project: str,
        pipeline_ids: list[int],
        batch_size: int = BATCH_SIZE,
    ) -> list[Pipeline]:
        """Fetches multiple pipelines in a project by their ID in batches asynchronously."""
        results = []
        total_pipelines = len(pipeline_ids)
        batch_count = (total_pipelines + batch_size - 1) // batch_size

        for batch_num, i in enumerate(range(0, total_pipelines, batch_size), 1):
            batch = pipeline_ids[i : i + batch_size]
            logging.info(
                "client: fetching batch %d/%d (%d pipelines)",
                batch_num,
                batch_count,
                len(batch),
            )

            tasks = [self.get_pipeline_by_id_async(project, pid) for pid in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            if i + batch_size < total_pipelines:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        return results

    def _get_pipeline_ids(self, project: str) -> list[int]:
        """Gets all pipeline IDs in a project."""
        url = f"{self.base_url}/{project}/_apis/pipelines"
        data = self._get(url)
        return [item["id"] for item in data.get("value", [])]

    async def _get_pipeline_ids_async(self, project: str) -> list[int]:
        """Gets all pipeline IDs in a project asynchronously."""
        url = f"{self.base_url}/{project}/_apis/pipelines"
        data = await self._get_async(url)
        return [item["id"] for item in data.get("value", [])]

    ### File methods
    def _get_file_content(
        self,
        project: str,
        repository: str,
        file_path: str,
        branch: str,
    ) -> str:
        """Retrieves the content of a file."""
        url = (
            f"{self.base_url}/{project}/_apis/git/repositories/{repository}/items"
            f"?path={quote(file_path)}"
            f"&versionDescriptor.version={quote(branch)}"
            f"&includeContent=true"
            f"&api-version={self.api_version}"
        )
        data = self._get(url)
        return data["content"]

    async def _get_file_content_async(
        self,
        project: str,
        repository: str,
        file_path: str,
        branch: str,
    ) -> str:
        """Retrieves the content of a file asynchronously."""
        url = (
            f"{self.base_url}/{project}/_apis/git/repositories/{repository}/items"
            f"?path={quote(file_path)}"
            f"&versionDescriptor.version={quote(branch)}"
            f"&includeContent=true"
            f"&api-version={self.api_version}"
        )
        data = await self._get_async(url)
        return data["content"]
