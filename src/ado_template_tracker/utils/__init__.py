"""Utility functions and components for Azure DevOps Template Tracker.

This package provides supporting utilities for scanning repositories,
processing YAML files, and other auxiliary operations needed by the
core template tracking functionality.

Components:
    RepositoryScanner: Scans Azure DevOps repositories for YAML files,
        supporting both full repository and specific directory traversal.

Example:
    ```python
    from ado_template_tracker.utils import RepositoryScanner
    from ado_template_tracker.core import AzureDevOpsClient, TemplateSource

    async def scan_repo():
        async with AzureDevOpsClient(organization="org", token="pat") as client:
            scanner = RepositoryScanner(client)

            source = TemplateSource(
                project="project",
                repository="repo",
                branch="main",
                directories=["/templates"]
            )

            # Returns list of (path, content) tuples
            yaml_files = await scanner.scan(source)
            return yaml_files
    ```
"""

from .scanner import RepositoryScanner

__all__ = ["RepositoryScanner"]
