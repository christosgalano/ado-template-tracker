import logging
from typing import Dict, List, Optional, Tuple

from client import AzureDevOpsClient
from model import TemplateSource


class RepositoryScanner:
    """Handles scanning of Azure DevOps repositories for YAML files."""

    def __init__(self, client: AzureDevOpsClient) -> None:
        self.client = client

    async def scan(self, source: TemplateSource) -> List[Tuple[str, str]]:
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
        self, source: TemplateSource
    ) -> List[Tuple[str, str]]:
        """Scan entire repository for YAML files."""
        logging.info(f"Scanning entire '{source.repository}' repository...")
        items = await self._get_repository_items(
            source=source, recursion_level="full", scope_path=None
        )
        return await self._process_yaml_files(items, source)

    async def _scan_directories(self, source: TemplateSource) -> List[Tuple[str, str]]:
        """Scan specific directories for YAML files."""
        all_files = []

        for directory in source.directories:
            if not directory.strip("/"):
                continue

            logging.info(f"Scanning directory {source.repository}/{directory}")

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
        scope_path: Optional[str] = None,
    ) -> List[Dict]:
        """Get repository items from Azure DevOps."""
        base_url = (
            f"{self.client.base_url}"
            f"/{source.project}"
            f"/_apis/git/repositories/{source.repository}/items"
        )
        params = {
            "recursionLevel": recursion_level,
            "version": source.branch,
            "versionType": "branch",
        }
        if scope_path:
            params["scopePath"] = scope_path

        logging.info(f"Getting repository items from {base_url}...")

        try:
            data = await self.client._get_async(url=base_url, params=params)
            return data.get("value", [])
        except Exception as e:
            logging.error(f"Failed to get repository items: {e}")
            return []

    async def _process_yaml_files(
        self, items: List[Dict], source: TemplateSource
    ) -> List[Tuple[str, str]]:
        """Process repository items to extract YAML files and their content."""
        yaml_files = []

        for item in items:
            if item.get("isFolder", False):
                continue

            path = item.get("path", "").lstrip("/")
            if not path.endswith((".yml", ".yaml")):
                continue

            try:
                content = await self.client._get_file_content_async(
                    source.project, source.repository, path, source.branch
                )
                yaml_files.append((path, content))
                logging.debug(f"Added YAML file: {path}")
            except Exception as e:
                logging.error(f"Failed to get content for {path}: {e}")

        return yaml_files
