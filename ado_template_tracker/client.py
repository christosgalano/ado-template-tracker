import asyncio
import concurrent.futures
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from urllib.parse import quote

import aiohttp
import requests
from azure.identity import DefaultAzureCredential
from model import Pipeline, Project, Repository
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AzureDevOpsClient:
    """Handles API interactions with Azure DevOps on a project level."""

    API_VERSION = "7.2-preview.1"  # Azure DevOps API version
    AZURE_DEVOPS_RESOURCE_ID = (
        "499b84ac-1321-427f-aa17-267ca6975798"  # Azure DevOps resource ID
    )
    MAX_RETRIES = 3  # Maximum number of retries for API requests
    RETRY_BACKOFF = 1  # Exponential backoff factor
    RETRY_STATUS_CODES = [500, 502, 503, 504]  # Retry on server errors
    BATCH_SIZE = 100  # Standard batch size for concurrent operations
    RATE_LIMIT_DELAY = 0.1  # 100ms delay between batches
    ASYNC_TOTAL_TIMEOUT = 30  # Total timeout for async requests
    ASYNC_CONNECT_TIMEOUT = 10  # Connection timeout for async requests
    ASYNC_SOCKET_TIMEOUT = 10  # Socket read timeout for async requests

    def __init__(
        self,
        organization: str,
        project: str,
        token: str = None,
        api_version: str = API_VERSION,
    ):
        # Base configuration
        self.organization = organization
        self.project = project
        self.api_version = api_version
        self.organization_base_url = f"https://dev.azure.com/{organization}"
        self.project_base_url = f"https://dev.azure.com/{organization}/{project}"

        # Authentication
        self.token = token or self.get_access_token()
        if not self.token:
            raise ValueError("Failed to retrieve an access token.")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

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
    def __enter__(self):
        """Context manager entry for sync operations."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit for sync operations."""
        if self._sync_session:
            self._sync_session.close()

    async def __aenter__(self):
        """Async context manager entry."""
        if self._async_session is None:
            self._async_session = await self._create_async_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._async_session:
            await self._async_session.close()
            self._async_session = None

    ### GET methods
    def _get(self, url: str, params: Dict = None) -> Dict:
        """Handles GET requests with error handling and JSON response."""
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed for {url}: {e}")
            raise

    async def _get_async(self, url: str, params: Dict = None) -> Dict:
        """Handles async GET requests with error handling."""
        session = await self.get_async_session()
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"Async API request failed for {url}: {e}")
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
        except requests.exceptions.RequestException as req_err:
            logging.error(f"HTTP error occurred while retrieving token: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error retrieving access token: {err}")
        return None

    ### Schema methods
    def get_pipeline_schema(self) -> Dict:
        """Gets the YAML schema for Azure DevOps pipelines from GitHub."""
        url = "https://raw.githubusercontent.com/Microsoft/azure-pipelines-vscode/main/service-schema.json"
        headers = {
            "Accept": "application/json",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch schema from GitHub: {e}")
            raise

    ### Project methods
    def list_projects(self) -> List[Project]:
        """Lists all projects in the organization."""
        url = f"{self.organization_base_url}/_apis/projects?api-version={self.api_version}"
        data = self._get(url)
        return [Project.from_get_response(item) for item in data.get("value", [])]

    async def list_projects_async(self) -> List[Project]:
        """Lists all projects in the organization asynchronously."""
        url = f"{self.organization_base_url}/_apis/projects?api-version={self.api_version}"
        data = await self._get_async(url)
        return [Project.from_get_response(item) for item in data.get("value", [])]

    def get_project_by_id(self, project_id: str) -> Project:
        """Gets details of a specific project."""
        url = f"{self.project_base_url}/_apis/projects/{project_id}?api-version={self.api_version}"
        data = self._get(url)
        return Project.from_get_response(data)

    async def get_project_by_id_async(self, project_id: str) -> Project:
        """Gets details of a specific project asynchronously."""
        url = f"{self.project_base_url}/_apis/projects/{project_id}?api-version={self.api_version}"
        data = await self._get_async(url)
        return Project.from_get_response(data)

    def get_project_by_name(self, project_name: str) -> Project:
        """Gets details of a specific project by name."""
        projects = self.list_projects()
        return next((p for p in projects if p.name == project_name), None)

    async def get_project_by_name_async(self, project_name: str) -> Project:
        """Gets details of a specific project by name asynchronously."""
        projects = await self.list_projects_async()
        return next((p for p in projects if p.name == project_name), None)

    ### Repository methods
    def list_repositories(self) -> List[Repository]:
        """Lists all repositories in the project."""
        url = f"{self.project_base_url}/_apis/git/repositories?api-version={self.api_version}"
        data = self._get(url)
        return [Repository.from_get_response(item) for item in data.get("value", [])]

    async def list_repositories_async(self) -> List[Repository]:
        """Lists all repositories in the project asynchronously."""
        url = f"{self.project_base_url}/_apis/git/repositories?api-version={self.api_version}"
        data = await self._get_async(url)
        return [Repository.from_get_response(item) for item in data.get("value", [])]

    def get_repository_by_id(self, repository_id: str) -> Repository:
        """Gets details of a specific repository."""
        url = f"{self.project_base_url}/_apis/git/repositories/{repository_id}?api-version={self.api_version}"
        data = self._get(url)
        return Repository.from_get_response(data)

    async def get_repository_by_id_async(self, repository_id: str) -> Repository:
        """Gets details of a specific repository asynchronously."""
        url = f"{self.project_base_url}/_apis/git/repositories/{repository_id}?api-version={self.api_version}"
        data = await self._get_async(url)
        return Repository.from_get_response(data)

    def get_repository_by_name(self, repository_name: str) -> Repository:
        """Gets details of a specific repository by name."""
        repositories = self.list_repositories()
        return next((r for r in repositories if r.name == repository_name), None)

    async def get_repository_by_name_async(self, repository_name: str) -> Repository:
        """Gets details of a specific repository by name asynchronously."""
        repositories = await self.list_repositories_async()
        return next((r for r in repositories if r.name == repository_name), None)

    ### Pipeline methods
    def list_pipelines(self) -> List[Pipeline]:
        """Lists all pipelines in a project with their full details and content."""
        pipeline_ids = self._get_pipeline_ids()
        return self._fetch_pipelines_by_ids(pipeline_ids)

    def list_pipelines_threaded(self, max_workers: int = 10) -> List[Pipeline]:
        """Lists all pipelines using threaded execution."""
        pipeline_ids = self._get_pipeline_ids()
        return self._fetch_pipelines_by_ids_threaded(pipeline_ids, max_workers)

    async def list_pipelines_async(self) -> List[Pipeline]:
        """Lists all pipelines asynchronously with their full details and content."""
        pipeline_ids = await self._get_pipeline_ids_async()
        return await self._fetch_pipelines_by_ids_async(pipeline_ids)

    def get_pipeline_by_id(self, pipeline_id: int) -> Pipeline:
        """Gets details of a specific pipeline."""
        url = f"{self.project_base_url}/_apis/pipelines/{pipeline_id}?api-version={self.api_version}"
        data = self._get(url)

        # Get pipeline content if path is available
        content = None
        if data.get("configuration", {}).get("path"):
            pipeline_name = data["name"]
            repo_id = data["configuration"]["repository"]["id"]
            path = data["configuration"]["path"]

            try:
                repo = self.get_repository_by_id(repo_id)
                logging.info(
                    f"Using default branch '{repo.default_branch}' for pipeline '{pipeline_name}' in repository '{repo.name}'"
                )
                content = self._get_file_content(repo.id, path, repo.default_branch)
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to get pipeline content: {e}")
                content = None

        return Pipeline.from_get_response(data, content)

    async def get_pipeline_by_id_async(self, pipeline_id: int) -> Pipeline:
        """Gets details of a specific pipeline asynchronously."""
        url = f"{self.project_base_url}/_apis/pipelines/{pipeline_id}?api-version={self.api_version}"
        data = await self._get_async(url)

        # Get pipeline content if path is available
        content = None
        if data.get("configuration", {}).get("path"):
            pipeline_name = data["name"]
            repo_id = data["configuration"]["repository"]["id"]
            path = data["configuration"]["path"]

            try:
                repo = await self.get_repository_by_id_async(repo_id)
                logging.info(
                    f"Using default branch '{repo.default_branch}' for pipeline '{pipeline_name}' in repository '{repo.name}'"
                )
                content = await self._get_file_content_async(
                    repo.id, path, repo.default_branch
                )
            except aiohttp.ClientError as e:
                logging.error(f"Failed to get pipeline content: {e}")
                content = None

        return Pipeline.from_get_response(data, content)

    def _fetch_pipelines_by_ids(self, pipeline_ids: List[int]) -> List[Pipeline]:
        """Fetches multiple pipelines by their ID in batches (synchronous)."""
        results = []
        total_pipelines = len(pipeline_ids)
        batch_count = (total_pipelines + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        logging.info(
            f"Starting synchronous fetch of {total_pipelines} pipelines in {batch_count} batches"
        )

        for batch_num, i in enumerate(range(0, total_pipelines, self.BATCH_SIZE), 1):
            batch = pipeline_ids[i : i + self.BATCH_SIZE]
            logging.info(
                f"Fetching batch {batch_num}/{batch_count} ({len(batch)} pipelines)"
            )

            batch_results = [self.get_pipeline_by_id(pid) for pid in batch]
            results.extend(batch_results)

            if batch_num < batch_count:
                time.sleep(self.RATE_LIMIT_DELAY)
                logging.info(f"Processed {len(results)}/{total_pipelines} pipelines")

        logging.info(f"Completed synchronous fetch of {len(results)} pipelines")
        return results

    def _fetch_pipelines_by_ids_threaded(
        self, pipeline_ids: List[int], max_workers: int = 10
    ) -> List[Pipeline]:
        """Fetches pipelines by their ID using thread pool."""
        total_pipelines = len(pipeline_ids)

        logging.info(
            f"Starting threaded fetch of {total_pipelines} pipelines with {max_workers} workers"
        )

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pid = {
                executor.submit(self.get_pipeline_by_id, pid): pid
                for pid in pipeline_ids
            }

            for future in concurrent.futures.as_completed(future_to_pid):
                pid = future_to_pid[future]
                try:
                    pipeline = future.result()
                    results.append(pipeline)
                    logging.info(
                        f"Fetched pipeline {pid} ({len(results)}/{total_pipelines})"
                    )
                except Exception as e:
                    logging.error(f"Failed to fetch pipeline {pid}: {e}")

        logging.info(f"Completed threaded fetch of {len(results)} pipelines")
        return results

    async def _fetch_pipelines_by_ids_async(
        self, pipeline_ids: List[int], batch_size: int = BATCH_SIZE
    ) -> List[Pipeline]:
        """Fetches multiple pipelines by their ID in batches asynchronously."""
        results = []
        total_pipelines = len(pipeline_ids)
        batch_count = (total_pipelines + batch_size - 1) // batch_size

        logging.info(
            f"Starting async fetch of {total_pipelines} pipelines in {batch_count} batches"
        )
        for batch_num, i in enumerate(range(0, total_pipelines, batch_size), 1):
            batch = pipeline_ids[i : i + batch_size]
            logging.info(
                f"Fetching batch {batch_num}/{batch_count} ({len(batch)} pipelines)"
            )

            tasks = [self.get_pipeline_by_id_async(pid) for pid in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            if i + batch_size < total_pipelines:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            logging.info(f"Processed {len(results)}/{total_pipelines} pipelines")

        logging.info(f"Completed async fetch of {len(results)} pipelines")
        return results

    def _get_pipeline_ids(self) -> List[int]:
        """Gets all pipeline IDs in the project."""
        url = f"{self.project_base_url}/_apis/pipelines?api-version={self.api_version}"
        data = self._get(url)
        return [item["id"] for item in data.get("value", [])]

    async def _get_pipeline_ids_async(self) -> List[int]:
        """Gets all pipeline IDs in the project asynchronously."""
        url = f"{self.project_base_url}/_apis/pipelines?api-version={self.api_version}"
        data = await self._get_async(url)
        return [item["id"] for item in data.get("value", [])]

    ### File methods
    def _get_file_content(self, repository_id: str, file_path: str, branch: str) -> str:
        """Retrieves the content of a file."""
        url = (
            f"{self.project_base_url}/_apis/git/repositories/{repository_id}/items"
            f"?path={quote(file_path)}"
            f"&versionDescriptor.version={quote(branch)}"
            f"&includeContent=true"
            f"&api-version={self.api_version}"
        )
        data = self._get(url)
        return data["content"]

    async def _get_file_content_async(
        self,
        repository_id: str,
        file_path: str,
        branch: str,
    ) -> str:
        """Retrieves the content of a file asynchronously."""
        url = (
            f"{self.project_base_url}/_apis/git/repositories/{repository_id}/items"
            f"?path={quote(file_path)}"
            f"&versionDescriptor.version={quote(branch)}"
            f"&includeContent=true"
            f"&api-version={self.api_version}"
        )
        data = await self._get_async(url)
        return data["content"]
