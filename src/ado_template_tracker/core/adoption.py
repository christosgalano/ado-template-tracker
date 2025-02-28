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
    - Optimized O(1) resource lookups via ID-based dictionaries
    - Memory-efficient batch processing for large datasets
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

        # Initialize data containers
        self._all_pipelines = []
        self._all_repositories = []
        self._all_projects = []
        self._organization = None

        try:
            # Step 1: Get source repository
            source_repository = await self.client.get_repository_async(self.source.project, self.source.repository)

            # Step 2: Load source templates
            await self._load_source_templates()
            if self.source.templates:
                logging.info(
                    "tracker: found %d templates in source repository",
                    len(self.source.templates),
                )

            # Step 3: Load target data based on scope
            await self._load_target_data()

            # Step 4: Check if target repository is the same as source repository, if not remove it from search
            if self._all_repositories:
                if len(self._all_repositories) == 1:
                    # Check if target repository is the same as source repository
                    if self._all_repositories[0].id == source_repository.id:
                        msg = "Target repository cannot be the same as source repository"
                        raise InitializationError(msg)  # noqa: TRY301
                else:
                    # Do not include source repository
                    self._all_repositories = [r for r in self._all_repositories if r.id != source_repository.id]

            # Step 5: Filter out pipelines without content
            self._all_pipelines = [p for p in self._all_pipelines if p.content]

            # Step 6: Initialize lookup dictionaries
            self._initialize_lookups()

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
            self._all_pipelines = await self._process_pipelines_in_batches(self._all_pipelines)

            # Build compliance hierarchy
            self._build_and_propagate_compliance()

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

    ### Initialization ###
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

    async def _load_target_data(self) -> None:
        """Load target data based on target scope."""
        loaders = {
            TargetScope.ORGANIZATION: self._load_organization_data,
            TargetScope.PROJECT: self._load_project_data,
            TargetScope.REPOSITORY: self._load_repository_data,
            TargetScope.PIPELINE: self._load_pipeline_data,
        }

        loader = loaders.get(self.target_scope)
        if not loader:
            msg = f"Unsupported target scope: {self.target_scope}"
            logging.error(msg)
            raise ValueError(msg)

        return await loader()

    async def _load_organization_data(self) -> None:
        """Load organization data with all projects, repositories, and pipelines."""
        self._organization = Organization(name=self.target.organization)

        self._all_projects = await self.client.list_projects_async()

        tasks = [self.client.list_pipelines_async(project.name) for project in self._all_projects]
        all_pipelines_results = await asyncio.gather(*tasks)
        self._all_pipelines = [pipeline for pipelines in all_pipelines_results for pipeline in pipelines]

        tasks = [self.client.list_repositories_async(project.name) for project in self._all_projects]
        all_repositories_results = await asyncio.gather(*tasks)
        self._all_repositories = [
            repository for repositories in all_repositories_results for repository in repositories
        ]

    async def _load_project_data(self) -> None:
        """Load project data with all repositories and pipelines."""
        project, self._all_pipelines, self._all_repositories = await asyncio.gather(
            self.client.get_project_async(self.target.project),
            self.client.list_pipelines_async(self.target.project),
            self.client.list_repositories_async(self.target.project),
        )
        self._all_projects = [project]

    async def _load_repository_data(self) -> None:
        """Load repository data with all pipelines."""
        repository, project, self._all_pipelines = await asyncio.gather(
            self.client.get_repository_async(self.target.project, self.target.repository),
            self.client.get_project_async(self.target.project),
            self.client.list_pipelines_async(self.target.project),
        )
        self._all_pipelines = [p for p in self._all_pipelines if p.repository_id == repository.id]
        self._all_repositories = [repository]
        self._all_projects = [project]

    async def _load_pipeline_data(self) -> None:
        """Load pipeline data for a single pipeline."""
        pipeline = await self.client.get_pipeline_by_id_async(
            self.target.project,
            self.target.pipeline_id,
        )
        self._all_pipelines = [pipeline]

    ### Resource Lookup ###
    def _initialize_lookups(self) -> None:
        """
        Initialize lookup dictionaries for fast ID-based access.

        Performance Note:
        These dictionaries are a critical performance optimization that enables
        O(1) lookups by ID instead of O(n) searches through lists. This is
        especially important when processing hundreds or thousands of pipelines
        that need to update their parent repositories and projects.
        """
        self._pipelines_dict = {pipeline.id: pipeline for pipeline in self._all_pipelines}
        self._repositories_dict = {repository.id: repository for repository in self._all_repositories}
        self._projects_dict = {project.id: project for project in self._all_projects}

    def _get_pipeline(self, pipeline_id: str) -> Pipeline | None:
        """Get pipeline by ID with proper error handling."""
        pipeline = next((p for p in self._all_pipelines if p.id == pipeline_id), None)
        if not pipeline:
            logging.warning("Pipeline with ID %s not found in lookup", pipeline_id)
            return None
        return pipeline

    def _get_repository(self, repository_id: str) -> Repository | None:
        """Get repository by ID with proper error handling."""
        repository = self._repositories_dict.get(repository_id)
        if not repository:
            logging.warning("Repository with ID %s not found in lookup", repository.id)
            return None
        return repository

    def _get_project(self, project_id: str) -> Project | None:
        """Get project by ID with proper error handling."""
        project = self._projects_dict.get(project_id)
        if not project:
            logging.warning("Project with ID %s not found in lookup", project_id)
            return None
        return project

    def _get_organization(self) -> Organization | None:
        """Get organization object with proper error handling."""
        if not self._organization:
            logging.warning("Organization not loaded")
            return None
        return self._organization

    ### Result Creation ###
    def _create_result(self) -> Organization | Project | Repository | Pipeline:
        """Create result object based on target scope."""
        creators = {
            TargetScope.ORGANIZATION: self._create_organization_result,
            TargetScope.PROJECT: self._create_project_result,
            TargetScope.REPOSITORY: self._create_repository_result,
            TargetScope.PIPELINE: self._create_pipeline_result,
        }

        creator = creators.get(self.target_scope)
        if not creator:
            msg = f"Unsupported target scope: {self.target_scope}"
            logging.error(msg)
            raise ValueError(msg)

        return creator()

    def _create_organization_result(self) -> Organization:
        """Create Organization result with metrics from all levels."""
        organization = self._get_organization()
        if not organization:
            msg = "Organization not loaded"
            raise InitializationError(msg)
        return organization

    def _create_project_result(self) -> Project:
        """Create Project result with metrics from pipelines and repositories."""
        if len(self._all_projects) != 1:
            msg = "Expected exactly one project for project scope"
            raise InitializationError(msg)
        return self._all_projects[0]

    def _create_repository_result(self) -> Repository:
        """Create Repository result with metrics from pipelines."""
        if len(self._all_repositories) != 1:
            msg = "Expected exactly one repository for repository scope"
            raise InitializationError(msg)
        return self._all_repositories[0]

    def _create_pipeline_result(self) -> Pipeline:
        """Create Pipeline result with metrics for a single pipeline."""
        if len(self._all_pipelines) != 1:
            msg = "Expected exactly one pipeline for pipeline scope"
            raise InitializationError(msg)
        return self._all_pipelines[0]

    ### Compliance  ###
    def _build_and_propagate_compliance(self) -> None:
        """Build compliance hierarchy by updating metrics across all levels."""
        # Step 0: Handle pipeline target scope
        if self.target_scope == TargetScope.PIPELINE:
            return

        # Step 1: Process pipeline compliance and update repositories/projects and optionally organization
        self._process_pipeline_compliance()

        # Step 2: Process repository compliance and update projects and optionally organization
        self._process_repository_compliance()

        # Step 3: Process project compliance and update organization
        if self.target_scope == TargetScope.ORGANIZATION:
            self._process_project_compliance()

    def _process_pipeline_compliance(self) -> None:
        """Process pipeline compliance and update repository, project, and optionally organization metrics."""
        for p in self._all_pipelines:
            repository = self._get_repository(p.repository_id)
            project = self._get_project(p.project_id)
            organization = self._get_organization()

            # Skip if repository or project not found
            if not repository or not project:
                continue

            # Update pipeline collections and counts
            if p.is_compliant():
                repository.compliant_pipelines.append(p)
                project.compliant_pipelines.append(p)
                if organization:
                    organization.compliant_pipelines.append(p)
            else:
                repository.non_compliant_pipelines.append(p)
                project.non_compliant_pipelines.append(p)
                if organization:
                    organization.non_compliant_pipelines.append(p)

            repository.total_no_pipelines += 1
            project.total_no_pipelines += 1
            if organization:
                organization.total_no_pipelines += 1

    def _process_repository_compliance(self) -> None:
        """Process repository compliance and update project and optionally organization metrics."""
        for repository in self._all_repositories:
            project = self._get_project(repository.project_id)
            organization = self._get_organization()

            # Skip if project not found
            if not project:
                continue

            # Update repository collections and counts
            if repository.is_compliant(self.compliance_mode):
                project.compliant_repositories.append(repository)
                if organization:
                    organization.compliant_repositories.append(repository)
            else:
                project.non_compliant_repositories.append(repository)
                if organization:
                    organization.non_compliant_repositories.append(repository)

            project.total_no_repositories += 1
            if organization:
                organization.total_no_repositories += 1

    def _process_project_compliance(self) -> None:
        """Process project compliance and update organization metrics."""
        for project in self._all_projects:
            organization = self._get_organization()
            if not organization:
                return

            # Update project collections and counts
            if project.is_compliant(self.compliance_mode):
                organization.compliant_projects.append(project)
            else:
                organization.non_compliant_projects.append(project)

            organization.total_no_projects += 1

    ### Pipeline Processing ###
    async def _process_pipelines_in_batches(self, pipelines: list[Pipeline], batch_size: int = 100) -> list[Pipeline]:
        """Process pipelines in batches to reduce memory pressure."""
        results = []
        for i in range(0, len(pipelines), batch_size):
            batch = pipelines[i : i + batch_size]
            logging.info(
                "Processing batch %d/%d (%d pipelines)",
                i // batch_size + 1,
                (len(pipelines) - 1) // batch_size + 1,
                len(batch),
            )
            results.extend(await self._process_pipelines(batch))
        return results

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

    ### Metrics Collection ###
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

    ### Source Repository Information ###
    def _get_source_repository_default_branch(self) -> str:
        """Gets the default branch of the source repository."""
        url = f"{self.client.base_url}/{self.source.project}/_apis/git/repositories/{self.source.repository}"
        data = self.client._get(url)  # noqa: SLF001
        return data["defaultBranch"].replace("refs/heads/", "")
