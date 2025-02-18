import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Union

import yaml
from client import AzureDevOpsClient
from model import (
    Adoption,
    AdoptionMetrics,
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

    MAX_CONCURRENT_REPOS = 5

    def __init__(
        self,
        client: AzureDevOpsClient,
        target: AdoptionTarget,
        source: TemplateSource,
    ) -> None:
        """
        Initialize the tracker with required configuration.

        Args:
            client: Azure DevOps client instance
            target: Where to look for template adoption
            source: Source templates to track
        """
        if not isinstance(client, AzureDevOpsClient):
            raise ValueError("client must be an instance of AzureDevOpsClient")
        if not source.repository:
            raise ValueError("source repository must be specified")

        self.client = client
        self.target = target
        self.source = source
        self.scanner = RepositoryScanner(self.client)
        self._project_pipelines: List[Pipeline] = []
        self._initialized = False

    @property
    def project_pipelines(self) -> List[Pipeline]:
        """Get project pipelines, ensuring initialization."""
        if not self._initialized:
            raise RuntimeError("Tracker not initialized. Call 'setup()' first.")
        return self._project_pipelines

    async def setup(self) -> None:
        """Setup the tracker by loading templates and pipelines."""
        if self._initialized:
            return

        try:
            # Load templates and pipelines concurrently
            pipelines, _ = await asyncio.gather(
                self.client.list_pipelines_async(self.target.project),
                self._load_source_templates(),
            )
            self._project_pipelines = pipelines
            self._initialized = True

            # Log actual number of templates found
            if self.source.templates:
                logging.info(
                    f"Found {len(self.source.templates)} templates in source repository"
                )
        except Exception as e:
            logging.error(f"Failed to initialize tracker: {e}")
            raise

    async def track(
        self,
    ) -> Tuple[Union[Project, Repository, Pipeline], AdoptionMetrics]:
        """Track template adoption and collect metrics."""
        # Ensure initialization
        await self.setup()

        # Start timing before actual processing
        start_time = time.perf_counter()

        # Process based on target type
        if self.target.pipeline_id is not None:
            result = await self._track_pipeline()
        elif self.target.repository is not None:
            result = await self._track_repository()
        else:
            result = await self._track_project()

        # Stop timing after processing, before metrics collection
        processing_time = time.perf_counter() - start_time

        # Collect metrics after timing
        if self.target.pipeline_id is not None:
            metrics = self._collect_pipeline_metrics(result)
        elif self.target.repository is not None:
            metrics = self._collect_repository_metrics(result)
        else:
            metrics = self._collect_project_metrics(result)

        # Set processing time after collection
        metrics.processing_time = processing_time

        return result, metrics

    async def _load_source_templates(self) -> None:
        """Load the template source configuration."""
        try:
            if self.source.template_path:
                self.source.templates = [self.source.template_path]
                return

            # Get all YAML files
            files = await self.scanner.scan(self.source)
            logging.info(f"Found {len(files)} potential template files")

            # Add templates and log count
            self.source.add_templates_from_directory(files)

        except Exception as e:
            logging.error(f"Failed to load template source: {e}")
            raise

    async def _track_project(self) -> Project:
        """Track template adoption across an entire project."""
        # Fetch project, repositories, and pipelines concurrently
        project, repositories = await asyncio.gather(
            self.client.get_project_async(self.target.project),
            self.client.list_repositories_async(self.target.project),
        )
        project.total_no_repositories = len(repositories)

        logging.info(
            f"Tracking project adoption for {len(self._project_pipelines)} pipelines in {project.total_no_repositories} repositories under {project.name} ..."
        )

        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REPOS)

        async def process_repo_with_limit(repo: Repository) -> Repository:
            """Process repository with concurrency limit."""
            async with semaphore:
                return await self._process_repository(repo)

        # Process repositories with concurrency limit
        tasks = [
            process_repo_with_limit(repo)
            for repo in repositories
            if not repo.is_disabled and repo.name != self.source.repository
        ]
        processed_repos = await asyncio.gather(*tasks)

        # Filter compliant repositories
        project.compliant_repositories = [
            repo for repo in processed_repos if repo.compliant_pipelines
        ]

        return project

    async def _track_repository(self) -> Repository:
        """Track template adoption in a specific repository."""
        repository = await self.client.get_repository_async(
            self.target.project, self.target.repository
        )
        return await self._process_repository(repository)

    async def _track_pipeline(self) -> Pipeline:
        """Track template adoption in a specific pipeline."""
        pipeline = await self.client.get_pipeline_by_id_async(
            self.target.project, self.target.pipeline_id
        )
        if pipeline.content:
            logging.info(
                f"Tracking pipeline adoption for pipeline {pipeline.name} ({pipeline.id})..."
            )
            adoption = self._parse_pipeline_content(pipeline.path, pipeline.content)
            pipeline.adoption = adoption
        return pipeline

    async def _process_repository(self, repo: Repository) -> Repository:
        """Process a repository to find template adoption in its pipelines."""
        repo_pipelines = [
            p for p in self._project_pipelines if p.repository_id == repo.id and p.path
        ]
        repo.total_no_pipelines = len(repo_pipelines)

        logging.info(
            f"Tracking repository adoption for {repo.total_no_pipelines} pipelines in {repo.name}..."
        )

        # Process pipelines concurrently
        tasks = [
            self._process_pipeline(pipeline)
            for pipeline in repo_pipelines
            if pipeline.content
        ]
        processed_pipelines = await asyncio.gather(*tasks)

        # Filter compliant pipelines
        repo.compliant_pipelines = [
            pipeline for pipeline in processed_pipelines if pipeline.adoption
        ]

        return repo

    async def _process_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """Process a single pipeline to detect template adoption."""
        if pipeline.content:
            pipeline.adoption = self._parse_pipeline_content(
                pipeline.path, pipeline.content
            )
        return pipeline

    def _parse_pipeline_content(self, path: str, content: str) -> Optional[Adoption]:
        """Parse pipeline YAML content to detect template usage."""
        try:
            pipeline_def = yaml.safe_load(content)
            if not isinstance(pipeline_def, dict):
                return None

            # Find source repository reference
            source_reference = self._find_source_reference(pipeline_def, path)
            if not source_reference:
                return None

            # Check for extends template
            if extends_template := self._find_extends_template(
                pipeline_def, source_reference
            ):
                return Adoption(
                    usage_type=UsageType.EXTEND, templates=[extends_template]
                )

            # Check for included templates
            if include_templates := self._find_include_templates(
                pipeline_def, source_reference
            ):
                return Adoption(
                    usage_type=UsageType.INCLUDE, templates=include_templates
                )

            return None

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML in {path}: {e}")
            return None

    def _find_source_reference(
        self, pipeline_def: dict, path: str
    ) -> Optional[Dict[str, str]]:
        """Find and validate source repository reference."""
        # Early returns for missing sections
        resources = pipeline_def.get("resources")
        if not resources:
            return None

        # Get repositories from resources
        if isinstance(resources, dict):
            repositories = resources.get("repositories", [])
        else:
            return None  # Invalid resources format
        if not repositories:
            return None

        source_default_branch = self._get_source_repository_default_branch()

        for repo in repositories:
            # If repository is not of type 'git', skip
            if repo.get("type", "") != "git":
                continue

            # Get repository name and validate format
            repo_name = repo.get("name", "")
            if not repo_name:
                continue

            # Parse project/repository from name
            project, repository = (
                repo_name.split("/", 1)
                if "/" in repo_name
                else (self.target.project, repo_name)
            )

            repo_ref = {
                "alias": repo.get("repository", ""),
                "ref": repo.get("ref", f"refs/heads/{source_default_branch}"),
                "project": project,
                "repository": repository,
            }

            # If repository does not match source, skip
            if (
                repo_ref["project"] != self.source.project
                or repo_ref["repository"] != self.source.repository
            ):
                continue

            # If repository branch does not match source, skip
            if repo_ref["ref"].replace("refs/heads/", "") != self.source.branch.replace(
                "refs/heads/", ""
            ):
                logging.warning(
                    f"Pipeline {path} references template repository "
                    f"'{repo.get('name')}' but uses different branch: "
                    f"{repo_ref['branch']} vs {self.source.branch}"
                )
                continue

            return repo_ref

        return None

    def _find_extends_template(
        self, pipeline_def: dict, source_reference: Dict[str, str]
    ) -> Optional[Template]:
        """Find and validate extends template."""
        if "extends" in pipeline_def:
            extends = pipeline_def["extends"]
            if isinstance(extends, dict) and "template" in extends:
                return self._create_template(extends["template"], source_reference)
        return None

    def _find_include_templates(
        self, pipeline_def: dict, source_reference: Dict[str, str]
    ) -> List[Template]:
        """Find and validate included templates."""
        template_paths = self._find_template_references(pipeline_def)
        if not template_paths:
            return []

        templates = []
        for template_path in template_paths:
            if template := self._create_template(template_path, source_reference):
                templates.append(template)
        return templates

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
        self, template_path: str, source_reference: Dict[str, str]
    ) -> Template:
        """
        Create a Template object from a template path.

        Args:
            template_path: Format 'path/to/template.yaml@alias'
            source_reference: Source repository reference
        """
        if "@" not in template_path:
            logging.debug(
                f"Skipping template without repository reference: {template_path}"
            )
            return None

        path, alias = template_path.split("@", 1)

        if alias != source_reference["alias"]:
            logging.warning(f"No repository reference found for alias '{alias}'")
            return None

        return Template(
            name=path.split("/")[-1],
            path=path,
            repository=source_reference["repository"],
            project=source_reference["project"],
        )

    def _collect_pipeline_metrics(self, pipeline: Pipeline) -> AdoptionMetrics:
        """Collect metrics for a single pipeline."""
        metrics = AdoptionMetrics(
            target_type="pipeline", target_name=f"{pipeline.name} ({pipeline.id})"
        )
        metrics.total_pipelines = 1

        if pipeline.adoption:
            metrics.compliant_pipelines = 1
            for template in pipeline.adoption.templates:
                metrics.add_template_usage(template.path)

        return metrics

    def _collect_repository_metrics(self, repository: Repository) -> AdoptionMetrics:
        """Collect metrics for a repository."""
        metrics = AdoptionMetrics(target_type="repository", target_name=repository.name)
        metrics.total_repositories = 1
        metrics.total_pipelines = repository.total_no_pipelines
        metrics.compliant_pipelines = len(repository.compliant_pipelines)
        metrics.compliant_repositories = 1 if repository.compliant_pipelines else 0

        for pipeline in repository.compliant_pipelines:
            if pipeline.adoption:
                for template in pipeline.adoption.templates:
                    metrics.add_template_usage(template.path)

        return metrics

    def _collect_project_metrics(self, project: Project) -> AdoptionMetrics:
        """Collect metrics for an entire project."""
        metrics = AdoptionMetrics(target_type="project", target_name=project.name)
        metrics.total_repositories = project.total_no_repositories
        metrics.compliant_repositories = len(project.compliant_repositories)

        for repo in project.compliant_repositories:
            metrics.total_pipelines += repo.total_no_pipelines
            metrics.compliant_pipelines += len(repo.compliant_pipelines)

            for pipeline in repo.compliant_pipelines:
                if pipeline.adoption:
                    for template in pipeline.adoption.templates:
                        metrics.add_template_usage(template.path)

        return metrics

    def _get_source_repository_default_branch(self) -> str:
        """Gets the default branch of the source repository."""
        url = f"{self.client.base_url}/{self.source.project}/_apis/git/repositories/{self.source.repository}"
        data = self.client._get(url)
        return data["defaultBranch"].replace("refs/heads/", "")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
