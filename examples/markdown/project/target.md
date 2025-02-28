# Project: CCHBC-Governance-Center

- Compliance Mode: ANY
- Compliance Status: Compliant
- Compliant Repositories: 33.3% (3/9)
- Compliant Pipelines: 44.4% (8/18)

## Repository Overview

| Repository | Compliance Rate |
|------------|-----------------|
| [administration](#administration) | 50.0% (6/12) |
| [policy-library](#policy-library) | 50.0% (1/2) |
| [terraform-template-repo](#terraform-template-repo) | 100.0% (1/1) |

## Repository Details

### administration

Compliant Pipelines: 50.0% (6/12)

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| administration/aad-group-myomada-creation | pipeline-library/terraform/deploy.yaml | include |
| administration/create-application-registration | pipeline-library/terraform/deploy.yaml | include |
| administration/create-project | pipeline-library/terraform/deploy.yaml | extend |
| administration/create-repository | pipeline-library/terraform/deploy.yaml | include |
| administration/create-self-hosted-agent | pipeline-library/terraform/deploy.yaml | include |
| administration/create-template-repository | pipeline-library/terraform/deploy.yaml | include |

### policy-library

Compliant Pipelines: 50.0% (1/2)

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| policy-library/policy-library-ci | pipeline-library/tools/install-tools.yaml | include |

### terraform-template-repo

Compliant Pipelines: 100.0% (1/1)

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| terraform-template-repo/terraform-template-repo-generate-docs | pipeline-library/terraform/generate-docs.yaml | extend |
