import logging
from typing import Dict, List, Optional

import yaml
from client import AzureDevOpsClient
from model import (
    Adoption,
    AdoptionTarget,
    Pipeline,
    Project,
    Repository,
    Template,
    TemplateSource,
    UsageType,
)
from repository_scanner import RepositoryScanner


class TemplateAdoptionTracker:
    """Tracks pipeline template adoption across various Azure DevOps scopes."""

    def __init__(
        self,
        client: AzureDevOpsClient,
        target: AdoptionTarget,
        template_source: TemplateSource,
    ):
        """
        Initialize the tracker with required configuration.

        Args:
            client: Azure DevOps client instance
            target: Where to look for template adoption
            template_source: Source templates to track
        """
        self.client = client
        self.target = target
        self.template_source = template_source
        self.scanner = RepositoryScanner(self.client)

    async def initialize(self) -> None:
        """Initialize the tracker by loading template sources."""
        await self._load_template_source()

    async def track(self) -> Project | Repository | Pipeline:
        """Track template adoption based on the configured target."""
        # Ensure templates are loaded before tracking
        if not self.template_source.templates:
            await self.initialize()

        if self.target.pipeline_id is not None:
            return await self._track_pipeline()
        elif self.target.repository_name is not None:
            return await self._track_repository()
        else:
            return await self._track_project()

    async def _load_template_source(self) -> None:
        """Load the template source configuration."""
        if self.template_source.template_path:
            self.template_source.templates = [self.template_source.template_path]
            return

        try:
            files = await self.scanner.scan(self.template_source)
            self.template_source.add_templates_from_directory(files)

        except Exception as e:
            logging.error(f"Failed to load template source: {e}")
            raise

    async def _track_project(self) -> Project:
        """Track template adoption across an entire project."""
        project = await self.client.get_project_by_name_async(self.target.project_name)
        repositories = await self.client.list_repositories_async()
        project.total_no_repositories = len(repositories)

        for repo in repositories:
            if not repo.is_disabled and repo.name != self.template_source.repository:
                repo_with_adoption = await self._process_repository(repo)
                if repo_with_adoption.compliant_pipelines:
                    project.compliant_repositories.append(repo_with_adoption)

        return project

    async def _track_repository(self) -> Repository:
        """Track template adoption in a specific repository."""
        repository = await self.client.get_repository_by_name_async(
            self.target.repository_name
        )
        return await self._process_repository(repository)

    async def _track_pipeline(self) -> Pipeline:
        """Track template adoption in a specific pipeline."""
        pipeline = await self.client.get_pipeline_by_id_async(self.target.pipeline_id)
        if pipeline.content:
            adoption = self._parse_pipeline_content(pipeline.path, pipeline.content)
            pipeline.adoption = adoption
        return pipeline

    async def _process_repository(self, repo: Repository) -> Repository:
        """Process a repository to find template adoption in its pipelines."""
        pipelines = await self.client.list_pipelines_async()
        repo_pipelines = [p for p in pipelines if p.repository_id == repo.id and p.path]
        repo.total_yaml_pipelines = len(repo_pipelines)

        for pipeline in repo_pipelines:
            if pipeline.content:
                adoption = self._parse_pipeline_content(pipeline.path, pipeline.content)
                if adoption and self._matches_template_source(adoption):
                    pipeline.adoption = adoption
                    repo.compliant_pipelines.append(pipeline)

        return repo

    def _parse_pipeline_content(self, path: str, content: str) -> Optional[Adoption]:
        """Parse pipeline YAML content to detect template usage."""

        try:
            pipeline_def = yaml.safe_load(content)
            if not isinstance(pipeline_def, dict):
                return None

            # Check for resources/repositories
            if "resources" in pipeline_def:
                if "repositories" in pipeline_def["resources"]:
                    repositories = pipeline_def["resources"]["repositories"]
                    for repo in repositories:
                        if repo["type"] == "git":
                            if "ref" in repo:
                                ref = repo["ref"]
                                if ref.startswith("refs/heads/"):
                                    branch = ref.replace("refs/heads/", "")
                                    if branch != self.template_source.branch:
                                        return None

            templates = []
            referenced_repos = []

            # If no resources are defined, return None
            if "resources" not in pipeline_def:
                return None

            # If no repositories are defined, return None
            if "repositories" not in pipeline_def["resources"]:
                return None

            repositories = pipeline_def["resources"]["repositories"]
            for repo in repositories:
                # If repository is not of type 'git', skip
                if repo.get("type", "") != "git":
                    continue

                repo_ref = {
                    "alias": repo.get("repository", ""),
                    "ref": repo.get("ref", "refs/heads/main"),
                    "project": repo.get("name", "").split("/")[0],
                    "repository": repo.get("name", "").split("/")[1],
                }

                # Extract branch name from ref
                if repo_ref["ref"].startswith("refs/heads/"):
                    repo_ref["branch"] = repo_ref["ref"].replace("refs/heads/", "")
                else:
                    repo_ref["branch"] = "main"

                # Check if current repository matches source
                if repo_ref["repository"] == self.template_source.repository:
                    if repo_ref["branch"] == self.template_source.branch:
                        referenced_repos.append(repo_ref)
                    else:
                        logging.warning(
                            f"Pipeline {path} references template repository "
                            f"'{repo.get('name')}' but uses different branch: "
                            f"{repo_ref['branch']} vs {self.template_source.branch}"
                        )

            # Check for 'extends' template
            if "extends" in pipeline_def:
                extends = pipeline_def["extends"]
                if isinstance(extends, dict) and "template" in extends:
                    templates.append(
                        self._create_template(extends["template"], referenced_repos)
                    )
                    return Adoption(usage_type=UsageType.EXTEND, templates=templates)

            # Check for '- template' references
            template_paths = self._find_template_references(pipeline_def)
            if template_paths:
                templates.extend(
                    self._create_template(template_path, referenced_repos)
                    for template_path in template_paths
                )
                return Adoption(usage_type=UsageType.INCLUDE, templates=templates)

            return None

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML in {path}: {e}")
            return None

    def _find_template_references(self, pipeline_def: dict) -> List[str]:
        """Recursively find template references in pipeline definition."""
        templates = []
        if isinstance(pipeline_def, dict):
            if "template" in pipeline_def:
                # Capture the template reference
                template_ref = pipeline_def["template"]
                if "@" in template_ref:  # Only interested in repository references
                    templates.append(template_ref)
            for value in pipeline_def.values():
                if isinstance(value, (dict, list)):
                    templates.extend(self._find_template_references(value))
        elif isinstance(pipeline_def, list):
            for item in pipeline_def:
                if isinstance(item, (dict, list)):
                    templates.extend(self._find_template_references(item))
        return templates

    def _create_template(
        self, template_path: str, referenced_repos: List[Dict[str, str]]
    ) -> Template:
        """
        Create a Template object from a template path.

        Args:
            template_path: Format 'path/to/template.yaml@alias'
            referenced_repos: Repository references from resources section
        """
        if "@" not in template_path:
            logging.debug(
                f"Skipping template without repository reference: {template_path}"
            )
            return None

        path, alias = template_path.split("@", 1)

        # Find the repository reference for this alias
        repo_ref = next((r for r in referenced_repos if r["alias"] == alias), None)

        if not repo_ref:
            logging.warning(f"No repository reference found for alias '{alias}'")
            return None

        return Template(
            name=path.split("/")[-1],
            path=path,
            repository=repo_ref["repository"],
            project=repo_ref["project"],
        )

    def _matches_template_source(self, adoption: Adoption) -> bool:
        """
        Check if adoption matches template source configuration.
        Only matches templates from the core repository.
        """
        for template in adoption.templates:
            if (
                template  # Handle None templates
                and template.project == self.template_source.project
                and template.repository == self.template_source.repository
                and template.path in self.template_source.templates
            ):
                logging.info(
                    f"Found matching template: {template.path} "
                    f"in {template.project}/{template.repository}"
                )
                return True
        return False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
