"""Repository scanning functionality for YAML files in Azure DevOps.

This module scans Azure DevOps repositories for YAML files, including pipeline
definitions and templates. It supports both full repository and directory-specific
scans with asynchronous operations for improved performance when dealing with
large repositories.

Key Components:
    RepositoryScanner: Orchestrates repository scanning with configurable
        filtering for YAML files, branch selection, and recursive directory traversal.

Features:
    - Full repository scanning
    - Specific directory/path filtering
    - Branch-specific scanning
    - Asynchronous operation
    - Automatic YAML file detection (.yml and .yaml extensions)

Dependencies:
    - core.client: AzureDevOpsClient for API communication
    - core.models: TemplateSource for scan configuration
    - logging: Operation logging and error handling

Example:
    ```python
    from ado_template_tracker.core.client import AzureDevOpsClient
    from ado_template_tracker.core.models import TemplateSource
    from ado_template_tracker.utils.scanner import RepositoryScanner

    async def scan_yaml_files():
        async with AzureDevOpsClient(
            organization="org",
            token="pat"
        ) as client:
            scanner = RepositoryScanner(client)

            # Configure source repository
            source = TemplateSource(
                project="project",
                repository="repo",
                branch="main",  # Specific branch to scan
                directories=["/templates", "/pipelines"]  # Multiple directories
            )

            # Scan for all YAML files
            yaml_files = await scanner.scan(source)
            print(f"Found {len(yaml_files)} YAML files")

            for path, content in yaml_files:
                print(f"File: {path} ({len(content)} bytes)")
    ```

Returns:
    List of tuples containing (file_path, file_content) for all YAML files
    matching the .yml or .yaml extension.

Raises:
    aiohttp.ClientError: When repository API requests fail
    ValueError: When source configuration is invalid (e.g., empty repository name)
    AttributeError: When client is not properly initialized
"""

import logging

from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.models import TemplateSource


class RepositoryScanner:
    """Handles scanning of Azure DevOps repositories for YAML files."""

    def __init__(self, client: AzureDevOpsClient) -> None:
        """Initializes the Scanner class with an AzureDevOpsClient instance."""
        self.client = client

    async def scan(self, source: TemplateSource) -> list[tuple[str, str]]:
        """
        Scan repository for YAML files, with automatic async/sync handling.

        Args:
            source: TemplateSource with the configuration for the scan

        Returns:
            List of tuples containing (file_path, file_content)
        """
        if not source.directories or source.directories == ["/"]:
            return await self._scan_entire_repository(source)
        return await self._scan_directories(source)

    async def _scan_entire_repository(
        self,
        source: TemplateSource,
    ) -> list[tuple[str, str]]:
        """Scan entire repository for YAML files."""
        logging.info("scanner: scanning entire '%s' repository...", source.repository)
        items = await self._get_repository_items(
            source=source,
            recursion_level="full",
            scope_path=None,
        )
        return await self._process_yaml_files(items, source)

    async def _scan_directories(self, source: TemplateSource) -> list[tuple[str, str]]:
        """Scan specific directories for YAML files."""
        all_files = []

        for directory in source.directories:
            if not directory.strip("/"):
                continue

            logging.info("scanner: scanning directory %s/%s", source.repository, directory)

            items = await self._get_repository_items(
                source=source,
                recursion_level="full",
                scope_path=directory.strip("/"),
            )

            files = await self._process_yaml_files(items, source)
            all_files.extend(files)

        return all_files

    async def _get_repository_items(
        self,
        source: TemplateSource,
        recursion_level: str,
        scope_path: str | None = None,
    ) -> list[dict]:
        """Get repository items from Azure DevOps."""
        base_url = f"{self.client.base_url}/{source.project}/_apis/git/repositories/{source.repository}/items"
        params = {
            "recursionLevel": recursion_level,
            "version": source.branch,
            "versionType": "branch",
        }
        if scope_path:
            params["scopePath"] = scope_path

        logging.info("scanner: getting repository items from %s...", base_url)

        try:
            data = await self.client._get_async(url=base_url, params=params)  # noqa: SLF001
            return data.get("value", [])
        except Exception:
            logging.exception("scanner: failed to get repository items")
            return []

    async def _process_yaml_files(
        self,
        items: list[dict],
        source: TemplateSource,
    ) -> list[tuple[str, str]]:
        """Process repository items to extract YAML files and their content."""
        yaml_files = []

        for item in items:
            if item.get("isFolder", False):
                continue

            path = item.get("path", "").lstrip("/")
            if not path.endswith((".yml", ".yaml")):
                continue

            try:
                content = await self.client._get_file_content_async(  # noqa: SLF001
                    source.project,
                    source.repository,
                    path,
                    source.branch,
                )
                yaml_files.append((path, content))
                logging.debug("scanner: added YAML file: %s", path)
            except Exception:
                logging.exception("scanner: failed to get content for %s", path)

        return yaml_files
