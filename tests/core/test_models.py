# ruff: noqa: E501,SLF001,PLR2004,C901,PLR0912,PLR0915

import pytest

from ado_template_tracker.core.exceptions import (
    InvalidComplianceModeError,
    InvalidTemplatePathError,
    InvalidViewModeError,
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
    ViewMode,
)


def test_template_source_add_templates_from_directory() -> None:
    """Test TemplateSource.add_templates_from_directory method."""
    source = TemplateSource(project="TestProject", repository="TestRepo")

    # Create test templates
    valid_template1 = (
        "templates/valid1.yaml",
        """
        steps:
          - script: echo "Valid template 1"
        """,
    )

    valid_template2 = (
        "templates/valid2.yaml",
        """
        jobs:
          - job: Test
            steps:
              - script: echo "Valid template 2"
        """,
    )

    invalid_template = (
        "templates/invalid.yaml",
        """
        random:
          key: value
        """,
    )

    # Add templates and check results
    source.add_templates_from_directory([valid_template1, valid_template2, invalid_template])

    # Should have added only valid templates
    if len(source.templates) != 2:
        pytest.fail(f"Expected 2 templates to be added, got {len(source.templates)}")
    if "templates/valid1.yaml" not in source.templates:
        pytest.fail("Expected templates/valid1.yaml to be added")
    if "templates/valid2.yaml" not in source.templates:
        pytest.fail("Expected templates/valid2.yaml to be added")
    if "templates/invalid.yaml" in source.templates:
        pytest.fail("Expected templates/invalid.yaml to be skipped")


def test_template_source_validation() -> None:
    """Test TemplateSource validation and initialization."""
    # Test valid initialization
    source = TemplateSource(project="TestProject", repository="TestRepo")
    if source.project != "TestProject":
        pytest.fail("Expected project to be 'TestProject'")
    if source.repository != "TestRepo":
        pytest.fail("Expected repository to be 'TestRepo'")

    # Test template path initialization
    source_with_template = TemplateSource(
        project="TestProject",
        repository="TestRepo",
        template_path="templates/test.yaml",
    )
    if source_with_template.templates != ["templates/test.yaml"]:
        pytest.fail("Expected templates list to contain the provided template_path")

    # Test invalid template path
    with pytest.raises(InvalidTemplatePathError):
        TemplateSource(
            project="TestProject",
            repository="TestRepo",
            template_path="templates/test.txt",  # Invalid extension
        )

    # Test conflicting configuration
    with pytest.raises(SourceConfigurationError):
        TemplateSource(
            project="TestProject",
            repository="TestRepo",
            template_path="templates/test.yaml",
            directories=["templates", "pipelines"],  # Conflict with template_path
        )


def test_template_source_is_valid_template_path() -> None:
    """Test TemplateSource._is_valid_template_path method."""
    source = TemplateSource(project="TestProject", repository="TestRepo")

    # Valid paths
    if not source._is_valid_template_path("templates/test.yaml"):
        pytest.fail("Expected templates/test.yaml to be valid")
    if not source._is_valid_template_path("pipelines/build.yml"):
        pytest.fail("Expected pipelines/build.yml to be valid")

    # Invalid paths
    if source._is_valid_template_path("templates/test.md"):
        pytest.fail("Expected templates/test.md to be invalid")
    if source._is_valid_template_path("pipelines/build.txt"):
        pytest.fail("Expected pipelines/build.txt to be invalid")


def test_template_source_is_in_specified_directories() -> None:
    """Test TemplateSource._is_in_specified_directories method."""
    # Default configuration (all directories)
    source = TemplateSource(project="TestProject", repository="TestRepo")

    if not source._is_in_specified_directories("any/path/file.yaml"):
        pytest.fail("Expected any path to be accepted with default configuration")

    # Custom directories
    source_custom = TemplateSource(
        project="TestProject",
        repository="TestRepo",
        directories=["templates", "pipelines"],
    )

    if not source_custom._is_in_specified_directories("templates/test.yaml"):
        pytest.fail("Expected templates/test.yaml to be in specified directories")
    if not source_custom._is_in_specified_directories("pipelines/build.yml"):
        pytest.fail("Expected pipelines/build.yml to be in specified directories")

    if source_custom._is_in_specified_directories("src/other.yaml"):
        pytest.fail("Expected src/other.yaml not to be in specified directories")


def test_template_source_is_valid_pipeline_template() -> None:
    """Test TemplateSource._is_valid_pipeline_template method."""
    source = TemplateSource(project="TestProject", repository="TestRepo")

    # Valid template with steps
    valid_steps_yaml = """
    parameters:
      name: string
    steps:
      - script: echo "Hello ${{ parameters.name }}"
    """
    is_valid, error = source._is_valid_pipeline_template(valid_steps_yaml)
    if not is_valid:
        pytest.fail(f"Expected valid steps template, got error: {error}")

    # Valid template with jobs
    valid_jobs_yaml = """
    jobs:
      - job: Build
        steps:
          - script: echo "Building..."
    """
    is_valid, error = source._is_valid_pipeline_template(valid_jobs_yaml)
    if not is_valid:
        pytest.fail(f"Expected valid jobs template, got error: {error}")

    # Invalid YAML with syntax error (unbalanced brackets)
    invalid_yaml = """
    {jobs:
      - job: Test
        steps:
          - script: echo "Testing..."
    """
    is_valid, error = source._is_valid_pipeline_template(invalid_yaml)
    if is_valid:
        pytest.fail("Expected invalid YAML to be rejected")

    # Not a template (no valid keys)
    not_template_yaml = """
    random:
      key: value
    """
    is_valid, error = source._is_valid_pipeline_template(not_template_yaml)
    if is_valid:
        pytest.fail("Expected non-template YAML to be rejected")


def test_compliance_mode_from_string() -> None:
    """Test ComplianceMode.from_string method."""
    if ComplianceMode.from_string("any") != ComplianceMode.ANY:
        pytest.fail("Expected 'any' to map to ComplianceMode.ANY")
    if ComplianceMode.from_string("majority") != ComplianceMode.MAJORITY:
        pytest.fail("Expected 'majority' to map to ComplianceMode.MAJORITY")
    if ComplianceMode.from_string("all") != ComplianceMode.ALL:
        pytest.fail("Expected 'all' to map to ComplianceMode.ALL")

    # Test case insensitivity
    if ComplianceMode.from_string("ANY") != ComplianceMode.ANY:
        pytest.fail("Expected 'ANY' to map to ComplianceMode.ANY")

    # Test invalid input
    with pytest.raises(
        InvalidComplianceModeError,
        match="Invalid compliance mode: invalid. Must be one of: any, majority, all",
    ):
        ComplianceMode.from_string("invalid")


def test_adoption_get_unique_templates() -> None:
    """Test Adoption.get_unique_templates method returns unique templates."""
    # Create a few templates
    template1 = Template(
        name="template1.yaml",
        path="templates/template1.yaml",
        repository="repo",
        project="project",
    )

    template2 = Template(
        name="template2.yaml",
        path="templates/template2.yaml",
        repository="repo",
        project="project",
    )

    # Create duplicate of template1 (same path, project, repository)
    template1_duplicate = Template(
        name="template1.yaml",
        path="templates/template1.yaml",
        repository="repo",
        project="project",
    )

    # Create adoption with duplicate templates
    adoption = Adoption(
        usage_type=UsageType.INCLUDE,
        templates=[template1, template2, template1_duplicate],
    )

    # Get unique templates
    unique_templates = adoption.get_unique_templates()

    # Check count of unique templates
    if len(unique_templates) != 2:
        pytest.fail(f"Expected 2 unique templates, got {len(unique_templates)}")

    # Check that each unique template is in the result
    template_paths = [t.path for t in unique_templates]
    if "templates/template1.yaml" not in template_paths:
        pytest.fail("Expected template1.yaml to be in the unique templates")
    if "templates/template2.yaml" not in template_paths:
        pytest.fail("Expected template2.yaml to be in the unique templates")

    # Verify that uniqueness is based on the object's equality (path, repository, project)
    # Create a different instance but with same values
    adoption2 = Adoption(
        usage_type=UsageType.EXTEND,
        templates=[template1, template1],
    )
    unique_templates2 = adoption2.get_unique_templates()
    if len(unique_templates2) != 1:
        pytest.fail(f"Expected 1 unique template when using identical templates, got {len(unique_templates2)}")


def test_adoption_metrics_add_template_usage() -> None:
    """Test AdoptionMetrics template usage tracking."""
    target = AdoptionTarget(organization="TestOrg", project="TestProject")
    metrics = AdoptionMetrics(target=target, compliance_mode=ComplianceMode.ANY)

    # Add template usage
    metrics.add_template_usage(
        template="templates/build.yml",
        project="Project1",
        repository="Repo1",
        pipeline="Pipeline1",
    )

    # Add another usage of the same template in a different pipeline
    metrics.add_template_usage(
        template="templates/build.yml",
        project="Project1",
        repository="Repo1",
        pipeline="Pipeline2",
    )

    # Add usage of a different template
    metrics.add_template_usage(
        template="templates/test.yml",
        project="Project2",
        repository="Repo2",
        pipeline="Pipeline3",
    )

    # Check template usage counts
    if metrics.template_usage.get("templates/build.yml") != 2:
        pytest.fail(
            f"Expected 2 usages of 'templates/build.yml', got {metrics.template_usage.get('templates/build.yml')}",
        )

    if metrics.template_usage.get("templates/test.yml") != 1:
        pytest.fail(f"Expected 1 usage of 'templates/test.yml', got {metrics.template_usage.get('templates/test.yml')}")

    # Check template project counts
    if metrics.get_template_project_count("templates/build.yml") != 1:
        pytest.fail(
            f"Expected 1 project using 'templates/build.yml', got {metrics.get_template_project_count('templates/build.yml')}",  # noqa:
        )

    if metrics.get_template_project_count("templates/test.yml") != 1:
        pytest.fail(
            f"Expected 1 project using 'templates/test.yml', got {metrics.get_template_project_count('templates/test.yml')}",
        )

    # Check template repository counts
    if metrics.get_template_repository_count("templates/build.yml") != 1:
        pytest.fail(
            f"Expected 1 repository using 'templates/build.yml', got {metrics.get_template_repository_count('templates/build.yml')}",
        )

    # Check template pipeline counts
    if metrics.get_template_pipeline_count("templates/build.yml") != 2:
        pytest.fail(
            f"Expected 2 pipelines using 'templates/build.yml', got {metrics.get_template_pipeline_count('templates/build.yml')}",
        )


def test_adoption_target_get_scope() -> None:
    """Test that AdoptionTarget correctly determines its scope."""
    # Test organization-level target
    org_target = AdoptionTarget(organization="TestOrg")
    if org_target.get_scope() != TargetScope.ORGANIZATION:
        pytest.fail(f"Expected organization scope, got {org_target.get_scope()}")

    # Test project-level target
    project_target = AdoptionTarget(organization="TestOrg", project="TestProject")
    if project_target.get_scope() != TargetScope.PROJECT:
        pytest.fail(f"Expected project scope, got {project_target.get_scope()}")

    # Test repository-level target
    repo_target = AdoptionTarget(
        organization="TestOrg",
        project="TestProject",
        repository="TestRepo",
    )
    if repo_target.get_scope() != TargetScope.REPOSITORY:
        pytest.fail(f"Expected repository scope, got {repo_target.get_scope()}")

    # Test pipeline-level target
    pipeline_target = AdoptionTarget(
        organization="TestOrg",
        project="TestProject",
        pipeline_id=123,
    )
    if pipeline_target.get_scope() != TargetScope.PIPELINE:
        pytest.fail(f"Expected pipeline scope, got {pipeline_target.get_scope()}")


def test_view_mode_values() -> None:
    """Test ViewMode enum functionality."""
    # Check enum values
    if not hasattr(ViewMode, "TARGET"):
        pytest.fail("ViewMode missing TARGET value")
    if not hasattr(ViewMode, "SOURCE"):
        pytest.fail("ViewMode missing SOURCE value")
    if not hasattr(ViewMode, "NON_COMPLIANT"):
        pytest.fail("ViewMode missing NON_COMPLIANT value")
    if not hasattr(ViewMode, "OVERVIEW"):
        pytest.fail("ViewMode missing OVERVIEW value")

    # Test string representation
    if str(ViewMode.TARGET) != "TARGET":
        pytest.fail(f"Expected ViewMode.TARGET to be 'TARGET', got '{ViewMode.TARGET!s}'")
    if str(ViewMode.SOURCE) != "SOURCE":
        pytest.fail(f"Expected ViewMode.SOURCE to be 'SOURCE', got '{ViewMode.SOURCE!s}'")
    if str(ViewMode.NON_COMPLIANT) != "NON_COMPLIANT":
        pytest.fail(f"Expected ViewMode.NON_COMPLIANT to be 'NON_COMPLIANT', got '{ViewMode.NON_COMPLIANT!s}'")
    if str(ViewMode.OVERVIEW) != "OVERVIEW":
        pytest.fail(f"Expected ViewMode.OVERVIEW to be 'OVERVIEW', got '{ViewMode.OVERVIEW!s}'")

    # Test from_string method if it exists
    if hasattr(ViewMode, "from_string"):
        if ViewMode.from_string("target") != ViewMode.TARGET:
            pytest.fail("ViewMode.from_string failed to convert 'target' to TARGET")
        if ViewMode.from_string("source") != ViewMode.SOURCE:
            pytest.fail("ViewMode.from_string failed to convert 'source' to SOURCE")
        if ViewMode.from_string("non_compliant") != ViewMode.NON_COMPLIANT:
            pytest.fail("ViewMode.from_string failed to convert 'non_compliant' to NON_COMPLIANT")
        if ViewMode.from_string("non-compliant") != ViewMode.NON_COMPLIANT:
            pytest.fail("ViewMode.from_string failed to convert 'non-compliant' to NON_COMPLIANT")
        if ViewMode.from_string("overview") != ViewMode.OVERVIEW:
            pytest.fail("ViewMode.from_string failed to convert 'overview' to OVERVIEW")

        # Test invalid input
        try:
            ViewMode.from_string("invalid_mode")
            pytest.fail("ViewMode.from_string should raise error for invalid input")
        except InvalidViewModeError:
            pass  # Expected behavior


def test_pipeline_from_get_response() -> None:
    """Test Pipeline.from_get_response method."""
    # Create sample API response
    api_response = {
        "id": 123,
        "name": "test-pipeline",
        "folder": "\\src\\pipelines",
        "configuration": {
            "path": "src/pipelines/test-pipeline.yml",
            "repository": {
                "id": "repo-id",
            },
        },
    }

    # Create pipeline from response
    pipeline = Pipeline.from_get_response(
        data=api_response,
        project_id="project-id",
        content="steps:\n  - script: echo 'test'",
    )

    # Verify pipeline properties
    if pipeline.id != 123:
        pytest.fail(f"Expected id 123, got {pipeline.id}")
    if pipeline.name != "test-pipeline":
        pytest.fail(f"Expected name 'test-pipeline', got {pipeline.name}")
    if pipeline.folder != "src\\pipelines":
        pytest.fail(f"Expected folder 'src\\pipelines', got {pipeline.folder}")
    if pipeline.path != "src/pipelines/test-pipeline.yml":
        pytest.fail(f"Expected path 'src/pipelines/test-pipeline.yml', got {pipeline.path}")
    if pipeline.project_id != "project-id":
        pytest.fail(f"Expected project_id 'project-id', got {pipeline.project_id}")
    if pipeline.repository_id != "repo-id":
        pytest.fail(f"Expected repository_id 'repo-id', got {pipeline.repository_id}")
    if pipeline.content != "steps:\n  - script: echo 'test'":
        pytest.fail(f"Expected content to be set correctly, got {pipeline.content}")


def test_pipeline_is_compliant() -> None:
    """Test Pipeline.is_compliant method."""
    # Pipeline without adoption
    pipeline_non_compliant = Pipeline(
        id=123,
        name="non-compliant",
        folder="src",
        path="src/non-compliant.yml",
    )
    if pipeline_non_compliant.is_compliant():
        pytest.fail("Expected non-compliant pipeline to return False")

    # Pipeline with adoption
    template = Template(
        name="template.yaml",
        path="templates/template.yaml",
        repository="repo",
        project="project",
    )
    adoption = Adoption(
        usage_type=UsageType.INCLUDE,
        templates=[template],
    )
    pipeline_compliant = Pipeline(
        id=456,
        name="compliant",
        folder="src",
        path="src/compliant.yml",
        adoption=adoption,
    )
    if not pipeline_compliant.is_compliant():
        pytest.fail("Expected compliant pipeline to return True")


def test_repository_from_get_response() -> None:
    """Test Repository.from_get_response method with various API response formats."""
    # Test with full API response
    full_response = {
        "id": "repo-id-123",
        "name": "test-repository",
        "defaultBranch": "refs/heads/main",
        "project": {
            "id": "project-id-456",
            "name": "Test Project",
        },
    }

    repo = Repository.from_get_response(full_response)

    if repo.id != "repo-id-123":
        pytest.fail(f"Expected id 'repo-id-123', got '{repo.id}'")
    if repo.name != "test-repository":
        pytest.fail(f"Expected name 'test-repository', got '{repo.name}'")
    if repo.default_branch != "main":  # Should strip refs/heads/ prefix
        pytest.fail(f"Expected default_branch 'main', got '{repo.default_branch}'")
    if repo.project_id != "project-id-456":
        pytest.fail(f"Expected project_id 'project-id-456', got '{repo.project_id}'")

    # Test with minimal API response and alternative branch format
    minimal_response = {
        "id": "minimal-repo",
        "name": "minimal-repo",
        "defaultBranch": "develop",  # No refs/heads/ prefix
        "project": {
            "id": "project-id",
        },
    }

    repo = Repository.from_get_response(minimal_response)

    if repo.id != "minimal-repo":
        pytest.fail(f"Expected id 'minimal-repo', got '{repo.id}'")
    if repo.default_branch != "develop":  # Should keep as is when no prefix
        pytest.fail(f"Expected default_branch 'develop', got '{repo.default_branch}'")
    if repo.project_id != "project-id":
        pytest.fail(f"Expected project_id 'project-id', got '{repo.project_id}'")

    # Test with missing defaultBranch
    no_branch_response = {
        "id": "no-branch-repo",
        "name": "no-branch-repo",
        "project": {
            "id": "project-id",
        },
    }

    repo = Repository.from_get_response(no_branch_response)

    if repo.id != "no-branch-repo":
        pytest.fail(f"Expected id 'no-branch-repo', got '{repo.id}'")
    if repo.default_branch != "":  # Should be empty string when no branch provided
        pytest.fail(f"Expected empty default_branch, got '{repo.default_branch}'")


def test_repository_is_compliant() -> None:
    """Test Repository.is_compliant method with different compliance modes."""
    repo = Repository(
        id="test-repo",
        name="test-repo",
        default_branch="main",
        project_id="test-project",
    )

    # Empty repository is never compliant
    if repo.is_compliant(ComplianceMode.ANY):
        pytest.fail("Expected empty repository not to be compliant")

    # Setup repository with 4 pipelines, 2 compliant
    repo.total_no_pipelines = 4
    repo.compliant_pipelines = [
        Pipeline(id=1, name="p1", folder="f"),
        Pipeline(id=2, name="p2", folder="f"),
    ]

    # Test ANY mode (should be compliant)
    if not repo.is_compliant(ComplianceMode.ANY):
        pytest.fail("Expected repository to be compliant with ANY mode")

    # Test MAJORITY mode (should be compliant with exactly 50%)
    if not repo.is_compliant(ComplianceMode.MAJORITY):
        pytest.fail("Expected repository to be compliant with MAJORITY mode at 50%")

    # Test ALL mode (should not be compliant)
    if repo.is_compliant(ComplianceMode.ALL):
        pytest.fail("Expected repository not to be compliant with ALL mode")

    # Make all pipelines compliant
    repo.compliant_pipelines = [
        Pipeline(id=1, name="p1", folder="f"),
        Pipeline(id=2, name="p2", folder="f"),
        Pipeline(id=3, name="p3", folder="f"),
        Pipeline(id=4, name="p4", folder="f"),
    ]

    # Test ALL mode again (should now be compliant)
    if not repo.is_compliant(ComplianceMode.ALL):
        pytest.fail("Expected repository to be compliant with ALL mode when all pipelines are compliant")


def test_repository_rates() -> None:
    """Test Repository pipeline_adoption_rate and pipeline_non_compliance_rate property."""
    repo = Repository(
        id="test-repo",
        name="test-repo",
        default_branch="main",
        project_id="test-project",
    )

    # Empty repository
    if repo.pipeline_adoption_rate != 0.0:
        pytest.fail(f"Expected empty repository to have 0% adoption, got {repo.pipeline_adoption_rate}%")
    if repo.pipeline_non_compliance_rate != 100.0:
        pytest.fail(f"Expected empty repository to have 100% non-compliance, got {repo.pipeline_non_compliance_rate}%")

    # 2 out of 5 pipelines are compliant (40%)
    repo.total_no_pipelines = 5
    repo.compliant_pipelines = [Pipeline(id=i, name=f"p{i}", folder="f") for i in range(1, 3)]
    repo.non_compliant_pipelines = [Pipeline(id=i, name=f"p{i}", folder="f") for i in range(3, 6)]

    if repo.pipeline_adoption_rate != 40.0:
        pytest.fail(f"Expected 40% adoption rate, got {repo.pipeline_adoption_rate}%")
    if repo.pipeline_non_compliance_rate != 60.0:
        pytest.fail(f"Expected 60% non-compliance rate, got {repo.pipeline_non_compliance_rate}%")

    # 5 out of 5 pipelines are compliant (100%)
    repo.compliant_pipelines = [Pipeline(id=i, name=f"p{i}", folder="f") for i in range(1, 6)]
    repo.non_compliant_pipelines = []
    if repo.pipeline_adoption_rate != 100.0:
        pytest.fail(f"Expected 100% adoption rate, got {repo.pipeline_adoption_rate}%")
    if repo.pipeline_non_compliance_rate != 0.0:
        pytest.fail(f"Expected 0% non-compliance rate, got {repo.pipeline_non_compliance_rate}%")


def test_project_from_get_response() -> None:
    """Test Project.from_get_response method."""
    # Create sample API response
    api_response = {
        "id": "project-id",
        "name": "Test Project",
        "description": "Test project description",
    }

    # Create project from response
    project = Project.from_get_response(api_response)

    # Verify project properties
    if project.id != "project-id":
        pytest.fail(f"Expected id 'project-id', got {project.id}")
    if project.name != "Test Project":
        pytest.fail(f"Expected name 'Test Project', got {project.name}")


def test_project_is_compliant() -> None:
    """Test Project.is_compliant method with different compliance modes."""
    project = Project(
        id="test-project",
        name="Test Project",
    )

    # Empty project is never compliant
    if project.is_compliant(ComplianceMode.ANY):
        pytest.fail("Expected empty project not to be compliant")

    # Setup project with 4 repositories, 2 compliant
    project.total_no_repositories = 4
    project.compliant_repositories = [
        Repository(id="repo1", name="repo1", default_branch="main"),
        Repository(id="repo2", name="repo2", default_branch="main"),
    ]

    # Test ANY mode (should be compliant)
    if not project.is_compliant(ComplianceMode.ANY):
        pytest.fail("Expected project to be compliant with ANY mode")

    # Test MAJORITY mode (should be compliant with exactly 50%)
    if not project.is_compliant(ComplianceMode.MAJORITY):
        pytest.fail("Expected project to be compliant with MAJORITY mode at 50%")

    # Test ALL mode (should not be compliant)
    if project.is_compliant(ComplianceMode.ALL):
        pytest.fail("Expected project not to be compliant with ALL mode")

    # Make all repositories compliant
    project.compliant_repositories = [
        Repository(id="repo1", name="repo1", default_branch="main"),
        Repository(id="repo2", name="repo2", default_branch="main"),
        Repository(id="repo3", name="repo3", default_branch="main"),
        Repository(id="repo4", name="repo4", default_branch="main"),
    ]

    # Test ALL mode again (should now be compliant)
    if not project.is_compliant(ComplianceMode.ALL):
        pytest.fail("Expected project to be compliant with ALL mode when all repositories are compliant")


def test_project_rates() -> None:
    """Test Project adoption and noncompliance rate properties."""
    project = Project(
        id="test-project",
        name="Test Project",
    )

    # NOTE: Compliance mode is implied to be ANY for these tests

    # Empty project
    if project.repository_adoption_rate != 0.0:
        pytest.fail(f"Expected empty project to have 0% repository adoption, got {project.repository_adoption_rate}%")
    if project.pipeline_adoption_rate != 0.0:
        pytest.fail(f"Expected empty project to have 0% pipeline adoption, got {project.pipeline_adoption_rate}%")

    if project.repository_non_compliance_rate != 100.0:
        pytest.fail(
            f"Expected empty project to have 100% repository non-compliance, got {project.repository_non_compliance_rate}%",
        )
    if project.pipeline_non_compliance_rate != 100.0:
        pytest.fail(
            f"Expected empty project to have 100% pipeline non-compliance, got {project.pipeline_non_compliance_rate}%",
        )

    # Set up repositories and pipelines
    # 3 out of 5 repositories are compliant (60%)
    project.total_no_repositories = 5
    project.total_no_pipelines = 10

    # Create repositories with pipelines
    repo1 = Repository(id="repo1", name="repo1", default_branch="main", project_id="test-project")
    repo1.total_no_pipelines = 3
    repo1.compliant_pipelines = [Pipeline(id=i, name=f"p{i}", folder="f") for i in range(1, 3)]
    repo1.non_compliant_pipelines = [Pipeline(id=3, name="p3", folder="f")]

    repo2 = Repository(id="repo2", name="repo2", default_branch="main", project_id="test-project")
    repo2.total_no_pipelines = 4
    repo2.compliant_pipelines = [Pipeline(id=i, name=f"p{i}", folder="f") for i in range(4, 7)]
    repo2.non_compliant_pipelines = [Pipeline(id=7, name="p7", folder="f")]

    repo3 = Repository(id="repo3", name="repo3", default_branch="main", project_id="test-project")
    repo3.total_no_pipelines = 3
    repo3.compliant_pipelines = [Pipeline(id=7, name="p7", folder="f")]
    repo3.non_compliant_pipelines = [Pipeline(id=i, name=f"p{i}", folder="f") for i in range(8, 10)]

    project.compliant_repositories = [repo1, repo2, repo3]
    project.non_compliant_repositories = [
        Repository(id=i, name=f"repo{i}", default_branch="main", project_id="test-project") for i in range(4, 6)
    ]
    project.compliant_pipelines = repo1.compliant_pipelines + repo2.compliant_pipelines + repo3.compliant_pipelines
    project.non_compliant_pipelines = (
        repo1.non_compliant_pipelines + repo2.non_compliant_pipelines + repo3.non_compliant_pipelines
    )

    # Check repository adoption rate (3/5 = 60%)
    if project.repository_adoption_rate != 60.0:
        pytest.fail(f"Expected 60% repository adoption rate, got {project.repository_adoption_rate}%")
    if project.repository_non_compliance_rate != 40.0:
        pytest.fail(f"Expected 40% repository non-compliance rate, got {project.repository_non_compliance_rate}%")

    # Check pipeline adoption rate (2+3+1=6 out of 10 = 60%)
    if project.pipeline_adoption_rate != 60.0:
        pytest.fail(f"Expected 60% pipeline adoption rate, got {project.pipeline_adoption_rate}%")
    if project.pipeline_non_compliance_rate != 40.0:
        pytest.fail(f"Expected 40% pipeline non-compliance rate, got {project.pipeline_non_compliance_rate}%")

    # Test with all repositories compliant (100%)
    repo4 = Repository(id="repo4", name="repo4", default_branch="main", project_id="test-project")
    repo4.total_no_pipelines = 0  # Empty repository, but still counts as a repository
    repo5 = Repository(id="repo5", name="repo5", default_branch="main", project_id="test-project")
    repo5.total_no_pipelines = 0  # Empty repository, but still counts as a repository
    project.compliant_repositories = [repo1, repo2, repo3, repo4, repo5]
    project.non_compliant_repositories = []

    # Check repository adoption rate (5/5 = 100%)
    if project.repository_adoption_rate != 100.0:
        pytest.fail(f"Expected 100% repository adoption rate, got {project.repository_adoption_rate}%")
    if project.repository_non_compliance_rate != 0.0:
        pytest.fail(f"Expected 0% repository non-compliance rate, got {project.repository_non_compliance_rate}%")

    # Pipeline adoption rate should remain the same (6/10 = 60%)
    if project.pipeline_adoption_rate != 60.0:
        pytest.fail(f"Expected 60% pipeline adoption rate, got {project.pipeline_adoption_rate}%")
    if project.pipeline_non_compliance_rate != 40.0:
        pytest.fail(f"Expected 40% pipeline non-compliance rate, got {project.pipeline_non_compliance_rate}%")


def test_organization_is_compliant() -> None:
    """Test Organization.is_compliant method with different compliance modes."""
    org = Organization(name="TestOrg")

    # Empty organization is never compliant
    if org.is_compliant(ComplianceMode.ANY):
        pytest.fail("Expected empty organization not to be compliant")

    # Setup organization with 4 projects, 2 compliant
    org.total_no_projects = 4
    org.compliant_projects = [
        Project(id="proj1", name="Project 1"),
        Project(id="proj2", name="Project 2"),
    ]

    # Test ANY mode (should be compliant)
    if not org.is_compliant(ComplianceMode.ANY):
        pytest.fail("Expected organization to be compliant with ANY mode")

    # Test MAJORITY mode (should be compliant with exactly 50%)
    if not org.is_compliant(ComplianceMode.MAJORITY):
        pytest.fail("Expected organization to be compliant with MAJORITY mode at 50%")

    # Test ALL mode (should not be compliant)
    if org.is_compliant(ComplianceMode.ALL):
        pytest.fail("Expected organization not to be compliant with ALL mode")

    # Make all projects compliant
    org.compliant_projects = [
        Project(id="proj1", name="Project 1"),
        Project(id="proj2", name="Project 2"),
        Project(id="proj3", name="Project 3"),
        Project(id="proj4", name="Project 4"),
    ]

    # Test ALL mode again (should now be compliant)
    if not org.is_compliant(ComplianceMode.ALL):
        pytest.fail("Expected organization to be compliant with ALL mode when all projects are compliant")


def test_organization_rates() -> None:
    """Test Organization adoption and noncompliance rate properties."""
    org = Organization(name="TestOrg")

    # Empty organization
    if org.project_adoption_rate != 0.0:
        pytest.fail(f"Expected empty organization to have 0% project adoption, got {org.project_adoption_rate}%")
    if org.repository_adoption_rate != 0.0:
        pytest.fail(f"Expected empty organization to have 0% repository adoption, got {org.repository_adoption_rate}%")
    if org.pipeline_adoption_rate != 0.0:
        pytest.fail(f"Expected empty organization to have 0% pipeline adoption, got {org.pipeline_adoption_rate}%")

    if org.project_non_compliance_rate != 100.0:
        pytest.fail(
            f"Expected empty organization to have 100% project non-compliance, got {org.project_non_compliance_rate}%",
        )
    if org.repository_non_compliance_rate != 100.0:
        pytest.fail(
            f"Expected empty organization to have 100% repository non-compliance, got {org.repository_non_compliance_rate}%",
        )
    if org.pipeline_non_compliance_rate != 100.0:
        pytest.fail(
            f"Expected empty organization to have 100% pipeline non-compliance, got {org.pipeline_non_compliance_rate}%",
        )

    # Setup organization with projects, repositories and pipelines
    org.total_no_projects = 4
    org.compliant_projects = [Project(id="proj1", name="Project 1"), Project(id="proj2", name="Project 2")]
    org.non_compliant_projects = [Project(id="proj3", name="Project 3"), Project(id="proj4", name="Project 4")]

    org.total_no_repositories = 10
    org.compliant_repositories = [
        Repository(id=f"repo{i}", name=f"Repo {i}", default_branch="main") for i in range(1, 6)
    ]
    org.non_compliant_repositories = [
        Repository(id=f"repo{i}", name=f"Repo {i}", default_branch="main") for i in range(6, 11)
    ]
    org.total_no_pipelines = 20
    org.compliant_pipelines = [Pipeline(id=i, name=f"Pipeline {i}", folder="src") for i in range(1, 11)]
    org.non_compliant_pipelines = [Pipeline(id=i, name=f"Pipeline {i}", folder="src") for i in range(11, 21)]

    # Check adoption rates
    if org.project_adoption_rate != 50.0:
        pytest.fail(f"Expected 50% project adoption rate, got {org.project_adoption_rate}%")
    if org.repository_adoption_rate != 50.0:
        pytest.fail(f"Expected 50% repository adoption rate, got {org.repository_adoption_rate}%")
    if org.pipeline_adoption_rate != 50.0:
        pytest.fail(f"Expected 50% pipeline adoption rate, got {org.pipeline_adoption_rate}%")

    # Check non-compliance rates
    if org.project_non_compliance_rate != 50.0:
        pytest.fail(f"Expected 50% project non-compliance rate, got {org.project_non_compliance_rate}%")
    if org.repository_non_compliance_rate != 50.0:
        pytest.fail(f"Expected 50% repository non-compliance rate, got {org.repository_non_compliance_rate}%")
    if org.pipeline_non_compliance_rate != 50.0:
        pytest.fail(f"Expected 50% pipeline non-compliance rate, got {org.pipeline_non_compliance_rate}%")
