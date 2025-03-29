# Dunder-Mifflin-Governance-Center

## Adoption Summary

- Scope: Project
- Mode: Any
- Status: Compliant
- Repository Adoption Rate: 33.3% (3/9)
- Pipeline Adoption Rate: 42.1% (8/19)

---

## Repository Overview

| Repository | Pipeline Adoption Rate |
|------------|-----------------|
| [administration](#administration) | 46.2% (6/13) |
| [policy-library](#policy-library) | 50.0% (1/2) |
| [terraform-template-repo](#terraform-template-repo) | 100.0% (1/1) |

---

## Repository Details

### administration

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `administration/aad-group-myomada-creation` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-application-registration` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-project` | `pipeline-library/terraform/deploy.yaml` | extend |
| `administration/create-repository` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-self-hosted-agent` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-template-repository` | `pipeline-library/terraform/deploy.yaml` | include |

### policy-library

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `policy-library/policy-library-ci` | `pipeline-library/tools/install-tools.yaml` | include |

### terraform-template-repo

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `terraform-template-repo/terraform-template-repo-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |
