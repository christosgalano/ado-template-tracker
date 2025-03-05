# Azure DevOps Template Tracker Guide

## Overview

The Azure DevOps Template Tracker is a specialized tool designed to monitor and analyze the adoption of pipeline templates across your Azure DevOps organization. Like a quality control inspector for your DevOps processes, it helps ensure consistency and standardization by tracking which projects, repositories, and pipelines are following established template patterns.

Why it matters: Using standard templates in your pipelines ensures consistency, reduces errors, and makes maintenance easier. This tool helps you identify areas where templates are being used properly and where adoption needs improvement.

## Component Analysis

### Source

**What it is**: The "Source" defines where your approved templates are located.

**In simple terms**: Think of the Source as your organization's "recipe book" of approved pipeline templates. It specifies where to find the standard templates that should be used across your projects.

**Key properties**:

- `Project`: The Azure DevOps project containing the templates
- `Repository`: The repository where templates are stored
- `Branch`: Which branch of the repository to check (default is "main")
- `Template Path`: An optional specific template to track
- `Directories`: Optional list of directories containing templates to track (defaults to the root of the repository)

> NOTE: Template path and directories are mutually exclusive. If you specify a template path you cannot specify directories, and vice versa.


**Example**:

`Source: Project-Y/pipeline-library (main branch)`

This means the tool will look for approved templates in the "pipeline-library" repository within the "CCHBC-Governance-Center" project, on the main branch.

### Target

**What it is**: The "Target" defines the scope of what you want to analyze for template adoption.

**In simple terms**: The Target is like choosing what part of your organization to inspect. It can be as broad as your entire organization or as specific as a single pipeline.

**Scope levels (from broadest to most specific)**:

1. `Organization`: Analyze all projects in your organization
2. `Project`: Analyze all repositories in a specific project
3. `Repository`: Analyze all pipelines in a specific repository
4. `Pipeline`: Analyze a single pipeline

**Example**:

`Target: Organization OrgX, Project Project-X`

This means the tool will analyze all repositories and pipelines within the "Project-X" project.

### Compliance Mode

**What it is**: "Compliance Mode" defines the threshold for considering a target compliant with template requirements.

**In simple terms**: This is how strict you want to be when determining if your projects/repositories/pipelines are following the template standards.

**Options**:

- **ANY**: The most lenient setting. A resource is compliant if at least one of its child resources uses templates.
  - An organization is compliant if any project is compliant
  - A project is compliant if any repository is compliant
  - A repository is compliant if any pipeline is compliant
- **MAJORITY**: A middle-ground setting. A resource is compliant if at least half of its child resources use templates.
  - An organization is compliant if 50% or more projects are compliant
  - A project is compliant if 50% or more repositories are compliant
  - A repository is compliant if 50% or more pipelines are compliant
- **ALL**: The strictest setting. A resource is compliant only if all of its child resources use templates.
  - An organization is compliant only if every project is compliant
  - A project is compliant only if every repository is compliant
  - A repository is compliant only if every pipeline is compliant

**Example**:

`Compliance Mode: ALL`

With this setting, a project is considered compliant only if all of its repositories have compliant pipelines. Each repository must have all pipelines using the approved templates to be considered compliant.

### View Mode

**What it is**: "View Mode" determines how the results are presented and organized.

**In simple terms**: This is how you want to look at your data - from different perspectives to answer different questions.

**Options**:

- **TARGET**: Organizes results by your Azure DevOps structure (organization → projects → repositories → pipelines)
  - Best for: Understanding which specific projects/repositories need improvement
- **SOURCE**: Organizes results by template usage (which templates are used where)
  - Best for: Analyzing which templates are most widely adopted
- **OVERVIEW**: Provides a high-level summary of adoption metrics and trends
  - Best for: Executive summaries and quick status checks
- **NON-COMPLIANT**: Shows only resources that aren't meeting compliance requirements
  - Best for: Identifying specific areas that need immediate attention

**Example**:

`View Mode: NON-COMPLIANT`

This will show only the resources that aren't meeting the compliance requirements, helping you focus remediation efforts.

## Pipeline Analysis


The provided [`track-pipeline-library-adoption.yaml`](/examples/pipelines/track-pipeline-library-adoption.yaml) pipeline allows you to run the template tracking tool directly in Azure DevOps, with results published as artifacts for easy access.

### How to Use the Pipeline

1. Set up the pipeline in your Azure DevOps project
2. Run the pipeline either manually or on a schedule (weekly by default)
3. Review the results in the published artifacts

### Default Settings

The pipeline comes with sensible defaults:

- Target: Whole organization (by default)
- Compliance Mode: "any" (lenient mode)
- View Mode: "target" (organized by Azure DevOps structure)
- Output Formats: Both JSON and Markdown reports are generated and uploaded as artifacts

### Required Parameters

When running the pipeline, the following parameters are required and must be provided:

| Parameter | Description |
|-----------|-------------|
| organization | Your Azure DevOps organization name |
| source_project | Project containing your template library |
| source_repository | Repository containing your templates |

Without these parameters, the pipeline cannot run successfully. All other parameters have reasonable defaults and are optional.

### Customizing the Pipeline

When running the pipeline, you can customize the following parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| target_project | Which project to analyze | (all projects) |
| target_repository | Specific repository to analyze | - (all repositories) |
| target_pipeline_id | Specific pipeline to analyze | 0 (all pipelines) |
| compliance_mode | Compliance threshold (any/majority/all) | any |
| view_mode | How results are displayed | target |
| source_branch | Template source branch | main |
| source_template | Specific template to track | - (all templates) |

### Example Use Cases

**Weekly Organization-wide Audit**:

- Use default settings with scheduled weekly runs
- Review results to monitor overall compliance

**Project-specific Analysis**:

- Set target_project to a specific project
- Run manually when needed

**Finding Non-compliant Resources**:

- Set view_mode to "non-compliant"
- Run to get a focused report on problem areas

**Template Adoption Analysis**:

- Set view_mode to "source"
- Run to analyze which templates are most widely used

By using this tool regularly, you can ensure that template adoption improves over time, leading to more consistent and maintainable pipeline definitions across your organization.
