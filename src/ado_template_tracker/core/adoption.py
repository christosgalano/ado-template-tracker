"""Core template adoption tracking functionality.

This module provides the central tracking logic for monitoring and analyzing
Azure DevOps pipeline template usage. It identifies which templates from a source
repository are being used across target projects, repositories, and pipelines,
measuring adoption rates and compliance with organizational standards.

Key Components:
    TemplateAdoptionTracker: Main class that orchestrates the tracking process,
        analyzing YAML pipelines for template references, calculating adoption
        metrics, and determining compliance status across different scopes.

Features:
    - Multi-level compliance assessment (organization/project/repository/pipeline)
    - Concurrent pipeline processing for performance
    - Detailed adoption metrics collection
    - Support for different compliance modes (ANY/MAJORITY/ALL)
    - Template usage pattern detection (extend/include)

Dependencies:
    - models: Data structures for Azure DevOps resources and adoption metrics
    - client: Azure DevOps API client for data retrieval
    - utils.scanner: Repository scanning for template discovery
    - yaml: YAML parsing for pipeline content analysis

Example:
    ```python
    from ado_template_tracker.core.adoption import TemplateAdoptionTracker
    from ado_template_tracker.core.client import AzureDevOpsClient
    from ado_template_tracker.core.models import AdoptionTarget, TemplateSource, ComplianceMode

    async def track_adoption():
        # Configure what templates to track
        source = TemplateSource(
            project="Templates",
            repository="PipelineTemplates",
            directories=["/build-templates", "/deploy-templates"]
        )

        # Configure where to look for adoption
        target = AdoptionTarget(
            organization="MyOrg",
            project="ProjectA"  # Analyze entire project
        )

        # Create tracker and analyze
        async with AzureDevOpsClient(organization="MyOrg", token="PAT") as client:
            tracker = TemplateAdoptionTracker(
                client=client,
                target=target,
                source=source,
                compliance_mode=ComplianceMode.MAJORITY,
            )

            # Get results and metrics
            result, metrics = await tracker.track()

            # Check compliance and adoption rates
            print(f"Project compliance: {result.is_compliant(ComplianceMode.MAJORITY)}")
            print(f"Adoption rate: {result.repository_adoption_rate:.2f}%")
    ```

Returns:
    The track() method returns a tuple containing:
    - Result object (Organization, Project, Repository, or Pipeline based on scope)
    - AdoptionMetrics with detailed usage statistics

Raises:
    InitializationError: When tracker fails to initialize
    InvalidClientError: When an invalid client is provided
    SourceConfigurationError: When source configuration is invalid
    TrackerNotInitializedError: When tracker is used before initialization
"""

import asyncio
import logging
import time

import yaml

from ado_template_tracker.core.client import AzureDevOpsClient
from ado_template_tracker.core.exceptions import (
    InitializationError,
    InvalidClientError,
    SourceConfigurationError,
)
from ado_template_tracker.core.models import (
    Adoption,
    AdoptionMetrics,
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
from ado_template_tracker.utils.scanner import RepositoryScanner


class TemplateAdoptionTracker:
    """Tracks pipeline template adoption across various Azure DevOps scopes."""

    MAX_CONCURRENT_PROCESSING = 10

    def __init__(
        self,
        client: AzureDevOpsClient,
        target: AdoptionTarget,
        source: TemplateSource,
        compliance_mode: ComplianceMode = ComplianceMode.ANY,
    ) -> None:
        """
        Initialize the tracker with required configuration.

        Args:
            client: Azure DevOps client instance
            target: Where to look for template adoption
            source: Source templates to track
            compliance_mode: Compliance mode for tracking (ANY, MAJORITY, ALL)
        """
        if not isinstance(client, AzureDevOpsClient):
            raise InvalidClientError
        if not source.repository:
            raise SourceConfigurationError

        self.client = client
        self.target = target
        self.target_scope = target.get_scope()
        self.source = source
        self.compliance_mode = compliance_mode
        self.scanner = RepositoryScanner(self.client)
        self._initialized = False

    async def setup(self) -> None:
        """Setup the tracker by loading data and templates."""
        if self._initialized:
            return

        try:
            # Get source repository and load templates
            source_repository, _ = await asyncio.gather(
                self.client.get_repository_async(self.source.project, self.source.repository),
                self._load_source_templates(),
            )
            if self.source.templates:
                logging.info(
                    "tracker: found %d templates in source repository",
                    len(self.source.templates),
                )

            if self.target_scope == TargetScope.ORGANIZATION:
                # Get all projects with all of their pipelines and repositories
                self._all_projects = await self.client.list_projects_async()
                tasks = [self.client.list_pipelines_async(project.name) for project in self._all_projects]
                all_pipelines_results = await asyncio.gather(*tasks)
                self._all_pipelines = [pipeline for pipelines in all_pipelines_results for pipeline in pipelines]
                tasks = [self.client.list_repositories_async(project.name) for project in self._all_projects]
                all_repositories_results = await asyncio.gather(*tasks)
                self._all_repositories = [
                    repository for repositories in all_repositories_results for repository in repositories
                ]
            elif self.target_scope == TargetScope.PROJECT:
                # Get project with all of its pipelines and repositories
                project, self._all_pipelines, self._all_repositories = await asyncio.gather(
                    self.client.get_project_async(self.target.project),
                    self.client.list_pipelines_async(self.target.project),
                    self.client.list_repositories_async(self.target.project),
                )
                self._all_projects = [project]
            elif self.target_scope == TargetScope.REPOSITORY:
                # Get repository with all of its pipelines
                repository, self._all_pipelines = await asyncio.gather(
                    self.client.get_repository_async(self.target.project, self.target.repository),
                    self.client.list_pipelines_async(self.target.project),
                )

                if repository.id == source_repository.id:
                    msg = "Target repository cannot be the same as source repository"
                    raise InitializationError(msg)  # noqa: TRY301

                self._all_pipelines = [p for p in self._all_pipelines if p.repository_id == repository.id]
                self._all_repositories = [repository]
                self._all_projects = []
            elif self.target_scope == TargetScope.PIPELINE:
                # Get pipeline
                pipeline = await self.client.get_pipeline_by_id_async(
                    self.target.project,
                    self.target.pipeline_id,
                )
                self._all_pipelines = [pipeline]
                self._all_repositories = []
                self._all_projects = []

            # Do not include source repository
            if self._all_repositories:
                self._all_repositories = [r for r in self._all_repositories if r.id != source_repository.id]

            # Only keep pipelines with content
            self._all_pipelines = [p for p in self._all_pipelines if p.content]

            # Create dictionaries for quick access
            self._projects_dict = {project.id: project for project in self._all_projects}
            self._repositories_dict = {repository.id: repository for repository in self._all_repositories}

            # Initialization complete
            self._initialized = True

        except Exception as e:
            logging.exception("tracker: failed to initialize tracker: %s")
            raise InitializationError from e

    async def track(
        self,
    ) -> tuple[Organization | Project | Repository | Pipeline, AdoptionMetrics]:
        """Track template adoption and collect metrics."""
        try:
            # Ensure initialization
            await self.setup()

            # Start timing before actual processing
            start_time = time.perf_counter()

            # Process all pipelines
            self._all_pipelines = await self._process_pipelines(self._all_pipelines)

            # Find all compliant pipelines
            self._compliant_pipelines = [p for p in self._all_pipelines if p.is_compliant()]

            # Set compliance on all levels
            self._set_compliance(self._compliant_pipelines)

            # Create result object
            result = self._create_result()

            # Stop timing after processing, before metrics collection
            processing_time = time.perf_counter() - start_time

            # Collect metrics after timing
            if self.target.pipeline_id is not None:
                metrics = self._collect_pipeline_metrics(result)
            elif self.target.repository is not None:
                metrics = self._collect_repository_metrics(result)
            elif self.target.project is not None:
                metrics = self._collect_project_metrics(result)
            else:
                metrics = self._collect_organization_metrics(result)

            metrics.target = self.target
            metrics.compliance_mode = self.compliance_mode
            metrics.processing_time = processing_time

            return result, metrics

        except Exception:
            logging.exception("tracker: failed to track template adoption")
            raise

    async def _load_source_templates(self) -> None:
        """Load the template source configuration."""
        try:
            if self.source.template_path:
                self.source.templates = [self.source.template_path]
                return

            # Get all YAML files
            files = await self.scanner.scan(self.source)
            logging.info("tracker: found %d potential template files", len(files))

            # Add templates and log count
            self.source.add_templates_from_directory(files)

        except Exception:
            logging.exception("tracker: failed to load template source")
            raise

    def _create_result(self) -> Organization | Project | Repository | Pipeline:
        """
        Create and populate a result object based on the target scope.

        This method creates the appropriate result object (Organization, Project, Repository,
        or Pipeline) and populates it with compliance metrics and overview based on the
        processed data.

        The result type depends on the target scope:
        - ORGANIZATION: Creates Organization with project/repository/pipeline metrics
        - PROJECT: Returns single processed project
        - REPOSITORY: Returns single processed repository
        - PIPELINE: Returns single processed pipeline

        Returns:
            Organization | Project | Repository | Pipeline: The populated result object
                matching the target scope type

        Raises:
            InitializationError: When scope-specific data validation fails:
                - PROJECT scope expects exactly one project
                - REPOSITORY scope expects exactly one repository
                - PIPELINE scope expects exactly one pipeline

        Example:
            ```
            # For Organization scope
            organization = _create_result()
            assert organization.total_no_projects == len(self._all_projects)
            assert organization.compliant_projects == len([p for p in projects if p.is_compliant()])

            # For Project scope
            project = _create_result()
            assert project.compliant_pipelines == [p for p in pipelines if p.is_compliant()]

            # For Repository scope
            repository = _create_result()
            assert repository.total_no_pipelines == len([p for p in pipelines if p.repository_id == repository.id])
            ```

        Notes:
            - Organization result includes aggregated metrics for all levels
            - For non-organization scopes, validates that exactly one target exists
            - Uses pre-calculated compliance data from _set_compliance()
            - Leverages list comprehensions for efficient filtering
        """
        if self.target_scope == TargetScope.ORGANIZATION:
            organization = Organization(name=self.target.organization)

            organization.total_no_projects = len(self._all_projects)
            organization.total_no_repositories = len(self._all_repositories)
            organization.total_no_pipelines = len(self._all_pipelines)

            organization.compliant_projects = [
                project for project in self._all_projects if project.is_compliant(self.compliance_mode)
            ]
            organization.compliant_repositories = [
                repo for repo in self._all_repositories if repo.is_compliant(self.compliance_mode)
            ]
            organization.compliant_pipelines = self._compliant_pipelines

            return organization

        if self.target_scope == TargetScope.PROJECT:
            if len(self._all_projects) != 1:
                msg = "Expected exactly one project for project scope"
                raise InitializationError(msg)
            return self._all_projects[0]

        if self.target_scope == TargetScope.REPOSITORY:
            if len(self._all_repositories) != 1:
                msg = "Expected exactly one repository for repository scope"
                raise InitializationError(msg)
            return self._all_repositories[0]

        # TargetScope.PIPELINE
        if len(self._all_pipelines) != 1:
            msg = "Expected exactly one pipeline for pipeline scope"
            raise InitializationError(msg)
        return self._all_pipelines[0]

    def _set_compliance(self, compliant_pipelines: list[Pipeline]) -> None:
        """
        Set compliance status and metrics across all hierarchical levels.

        This method efficiently updates compliance information in a single pass through
        the data, setting metrics for repositories and projects based on their
        contained pipelines.

        Flow:
        1. Update repository metrics:
           - Set compliant pipelines list
           - Calculate total pipeline count
        2. Update project metrics:
           - Set compliant pipelines list
           - Calculate total pipeline count
           - Calculate repository counts
           - Set compliant repositories list

        Performance Considerations:
        - Processes all levels in a single pass
        - Uses list comprehensions for efficient filtering
        - Avoids redundant calculations
        - Leverages pre-filtered compliant pipelines list

        Args:
            compliant_pipelines: List of pipelines that meet compliance criteria
                               (already filtered by is_compliant())

        Example Hierarchy:
            Project
            ├── Repository 1
            │   ├── Pipeline A (compliant)
            │   └── Pipeline B (non-compliant)
            └── Repository 2
                ├── Pipeline C (compliant)
                └── Pipeline D (compliant)

            Results in:
            - Repository 1: 50% compliance (1/2 pipelines)
            - Repository 2: 100% compliance (2/2 pipelines)
            - Project: Both metrics plus repository compliance
        """
        # For each repository, set compliant pipelines and total pipelines.
        # This covers the following scopes: organization, project, repository
        for repository in self._all_repositories:
            repository.compliant_pipelines = [p for p in compliant_pipelines if p.repository_id == repository.id]
            repository.total_no_pipelines = len(
                [p for p in self._all_pipelines if p.repository_id == repository.id],
            )

        # For each project, set compliant pipelines, total pipelines, compliant repositories, and total repositories (repositories are already set)  # noqa: E501
        # This covers the following scopes: organization, project
        for project in self._all_projects:
            project.compliant_pipelines = [
                p
                for p in compliant_pipelines
                if p.project_id == project.id  # repositories already set
            ]
            project.compliant_repositories = [
                r for r in self._all_repositories if r.project_id == project.id and r.is_compliant(self.compliance_mode)
            ]
            project.total_no_pipelines = len([p for p in self._all_pipelines if p.project_id == project.id])
            project.total_no_repositories = len([r for r in self._all_repositories if r.project_id == project.id])

    async def _process_pipelines(self, pipelines: list[Pipeline]) -> list[Pipeline]:
        """Process given pipelines and set their adoption field."""
        logging.info("tracker: processing %d pipelines...", len(self._all_pipelines))

        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PROCESSING)

        async def process_pipeline_with_limit(pipeline: Pipeline) -> Pipeline:
            """Process pipeline with concurrency limit."""
            async with semaphore:
                return await self._process_pipeline(pipeline)

        # Process pipelines with concurrency limit
        tasks = [process_pipeline_with_limit(pipeline) for pipeline in pipelines]
        return await asyncio.gather(*tasks)

    async def _process_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """Process a single pipeline and set its adoption field."""
        if pipeline.content:
            pipeline.adoption = self._parse_pipeline_content(
                pipeline.path,
                pipeline.content,
            )
        return pipeline

    def _parse_pipeline_content(self, path: str, content: str) -> Adoption | None:
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
            if extends_template := self._find_extend_template(
                pipeline_def,
                source_reference,
            ):
                return Adoption(
                    usage_type=UsageType.EXTEND,
                    templates=[extends_template],
                )

            # Check for included templates
            if include_templates := self._find_include_templates(
                pipeline_def,
                source_reference,
            ):
                return Adoption(
                    usage_type=UsageType.INCLUDE,
                    templates=include_templates,
                )

            return None

        except yaml.YAMLError:
            logging.exception("tracker: error parsing YAML in %s", path)
            return None

    def _find_source_reference(
        self,
        pipeline_def: dict,
        path: str,
    ) -> dict[str, str] | None:
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
            project, repository = repo_name.split("/", 1) if "/" in repo_name else (self.target.project, repo_name)

            repo_ref = {
                "alias": repo.get("repository", ""),
                "ref": repo.get("ref", f"refs/heads/{source_default_branch}"),
                "project": project,
                "repository": repository,
            }

            # If repository does not match source, skip
            if repo_ref["project"] != self.source.project or repo_ref["repository"] != self.source.repository:
                continue

            # If repository branch does not match source, skip
            if repo_ref["ref"].replace("refs/heads/", "") != self.source.branch.replace(
                "refs/heads/",
                "",
            ):
                logging.warning(
                    "tracker: pipeline %s references template repository '%s' but uses different branch: %s vs %s",
                    path,
                    repo.get("name"),
                    repo_ref["ref"],
                    self.source.branch,
                )
                continue

            return repo_ref

        return None

    def _find_extend_template(
        self,
        pipeline_def: dict,
        source_reference: dict[str, str],
    ) -> Template | None:
        """Find and validate extends template."""
        if "extends" in pipeline_def:
            extends = pipeline_def["extends"]
            if isinstance(extends, dict) and "template" in extends:
                return self._create_template(extends["template"], source_reference)
        return None

    def _find_include_templates(
        self,
        pipeline_def: dict,
        source_reference: dict[str, str],
    ) -> list[Template]:
        """Find and validate included templates."""
        template_paths = self._find_template_references(pipeline_def)
        if not template_paths:
            return []

        return [
            template
            for template_path in template_paths
            if (template := self._create_template(template_path, source_reference))
        ]

    def _find_template_references(self, pipeline_def: dict) -> list[str]:
        """Recursively find template references in pipeline definition."""
        templates = []
        if isinstance(pipeline_def, dict):
            if "template" in pipeline_def:
                # Capture the template reference
                template_ref = pipeline_def["template"]
                if "@" in template_ref:  # Only interested in repository references
                    templates.append(template_ref)
            for value in pipeline_def.values():
                if isinstance(value, dict | list):
                    templates.extend(self._find_template_references(value))
        elif isinstance(pipeline_def, list):
            for item in pipeline_def:
                if isinstance(item, dict | list):
                    templates.extend(self._find_template_references(item))
        return templates

    def _create_template(
        self,
        template_path: str,
        source_reference: dict[str, str],
    ) -> Template:
        """
        Create a Template object from a template path.

        Args:
            template_path: Format 'path/to/template.yaml@alias'
            source_reference: Source repository reference
        """
        if "@" not in template_path:
            logging.debug(
                "tracker: skipping template without repository reference: %s",
                template_path,
            )
            return None

        path, alias = template_path.split("@", 1)

        if path not in self.source.templates:
            logging.debug("tracker: skipping template not found in source: %s", path)
            return None

        if alias != source_reference["alias"]:
            logging.warning("tracker: no repository reference found for alias '%s'", alias)
            return None

        return Template(
            name=path.split("/")[-1],
            path=path,
            repository=source_reference["repository"],
            project=source_reference["project"],
        )

    def _collect_pipeline_metrics(self, pipeline: Pipeline) -> AdoptionMetrics:
        """Collect metrics for a single pipeline."""
        metrics = AdoptionMetrics(target=self.target, compliance_mode=self.compliance_mode)
        if pipeline.is_compliant():
            for template in pipeline.adoption.templates:
                metrics.add_template_usage(
                    template=template.path,
                )
        return metrics

    def _collect_repository_metrics(self, repository: Repository) -> AdoptionMetrics:
        """Collect metrics for a repository."""
        metrics = AdoptionMetrics(target=self.target, compliance_mode=self.compliance_mode)
        for pipeline in repository.compliant_pipelines:
            for template in pipeline.adoption.templates:
                metrics.add_template_usage(
                    template=template.path,
                    pipeline=pipeline.name,
                )
        return metrics

    def _collect_project_metrics(self, project: Project) -> AdoptionMetrics:
        """Collect metrics for an entire project."""
        metrics = AdoptionMetrics(target=self.target, compliance_mode=self.compliance_mode)
        for pipeline in project.compliant_pipelines:
            for template in pipeline.adoption.templates:
                metrics.add_template_usage(
                    template=template.path,
                    repository=self._repositories_dict[pipeline.repository_id].name,
                    pipeline=pipeline.name,
                )
        return metrics

    def _collect_organization_metrics(self, organization: Organization) -> AdoptionMetrics:
        """Collect metrics for an entire organization."""
        metrics = AdoptionMetrics(target=self.target, compliance_mode=self.compliance_mode)
        for pipeline in organization.compliant_pipelines:
            for template in pipeline.adoption.templates:
                metrics.add_template_usage(
                    template=template.path,
                    project=self._projects_dict[pipeline.project_id].name,
                    repository=self._repositories_dict[pipeline.repository_id].name,
                    pipeline=pipeline.name,
                )
        return metrics

    def _get_source_repository_default_branch(self) -> str:
        """Gets the default branch of the source repository."""
        url = f"{self.client.base_url}/{self.source.project}/_apis/git/repositories/{self.source.repository}"
        data = self.client._get(url)  # noqa: SLF001
        return data["defaultBranch"].replace("refs/heads/", "")

    async def __aenter__(self) -> "TemplateAdoptionTracker":
        """Async context manager entry."""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
