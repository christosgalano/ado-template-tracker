# Dunder-Mifflin

## Adoption Summary

- Scope: Organization
- Mode: Any
- Status: Compliant
- Project Adoption Rate: 50.0% (2/4)
- Repository Adoption Rate: 3.5% (14/404)
- Pipeline Adoption Rate: 4.5% (38/848)

---

## Project Overview

| Project | Repository Adoption Rate | Pipeline Adoption Rate |
|---------|------------------------|---------------------|
| [Dunder-Mifflin-Governance-Center](#dunder-miflinbc-governance-center) | 33.3% (3/9) | 42.1% (8/19) |
| [Project-X](#dunder-miflin-safe-portfolio) | 3.0% (11/369) | 3.7% (30/817) |

---

## Project Details

### Dunder-Mifflin-Governance-Center

#### Repository Overview

| Repository | Pipeline Adoption Rate |
|------------|-----------------|
| [administration](#administration) | 46.2% (6/13) |
| [policy-library](#policy-library) | 50.0% (1/2) |
| [terraform-template-repo](#terraform-template-repo) | 100.0% (1/1) |

#### Repository Details

##### administration

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `administration/aad-group-myomada-creation` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-application-registration` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-project` | `pipeline-library/terraform/deploy.yaml` | extend |
| `administration/create-repository` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-self-hosted-agent` | `pipeline-library/terraform/deploy.yaml` | include |
| `administration/create-template-repository` | `pipeline-library/terraform/deploy.yaml` | include |

##### policy-library

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `policy-library/policy-library-ci` | `pipeline-library/tools/install-tools.yaml` | include |

##### terraform-template-repo

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `terraform-template-repo/terraform-template-repo-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

---

### Project-X

#### Repository Overview

| Repository | Pipeline Adoption Rate |
|------------|-----------------|
| [ruiet-vmi-infrastructure](#ruiet-vmi-infrastructure) | 100.0% (3/3) |
| [drew-ai-phoenix](#drew-ai-phoenix) | 100.0% (3/3) |
| [th-cloud-cloudformation-terraform](#th-cloud-cloudformation-terraform) | 100.0% (3/3) |
| [th-cloud-itdcmint](#th-cloud-itdcmint) | 100.0% (3/3) |
| [th-cloud-ot-lz](#th-cloud-ot-lz) | 100.0% (3/3) |
| [th-cloud-pus-bw](#th-cloud-pus-bw) | 100.0% (3/3) |
| [th-cloud-pus-bwjava](#th-cloud-pus-bwjava) | 100.0% (3/3) |
| [th-cloud-pus-crm](#th-cloud-pus-crm) | 100.0% (2/2) |
| [th-cloud-saplumira](#th-cloud-saplumira) | 100.0% (3/3) |
| [th-cloud-pus-s4](#th-cloud-pus-s4) | 100.0% (3/3) |
| [th-cloud-pus-slt](#th-cloud-pus-slt) | 100.0% (1/1) |

#### Repository Details

##### ruiet-vmi-infrastructure

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `RUIET/ruiet-vmi-infrastructure/ruiet-vmi-infrastructure-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `RUIET/ruiet-vmi-infrastructure/ruiet-vmi-infrastructure-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `RUIET/ruiet-vmi-infrastructure/ruiet-vmi-infrastructure-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### drew-ai-phoenix

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `DTT/drew-ai-phoenix/drew-ai-phoenix-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `DTT/drew-ai-phoenix/drew-ai-phoenix-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `DTT/drew-ai-phoenix/drew-ai-phoenix-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### th-cloud-cloudformation-terraform

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/th-cloud-cloudformation-terraform/th-cloud-cloudformation-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/th-cloud-cloudformation-terraform/th-cloud-cloudformation-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `agg/th-cloud-cloudformation-terraform/th-cloud-cloudformation-terraform-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### th-cloud-itdcmint

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/th-cloud-itdcmint/th-cloud-itdcmint-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/th-cloud-itdcmint/th-cloud-itdcmint-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `agg/th-cloud-itdcmint/th-cloud-itdcmint-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### th-cloud-ot-lz

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/Cloud Services/OT-LZ/th-cloud-ot-lz-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/Cloud Services/OT-LZ/th-cloud-ot-lz-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `agg/Cloud Services/OT-LZ/th-cloud-ot-lz-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### th-cloud-pus-bw

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/Cloud Services/SAP-BW/th-cloud-pus-bw-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/Cloud Services/SAP-BW/th-cloud-pus-bw-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `agg/Cloud Services/SAP-BW/th-cloud-pus-bw-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### th-cloud-pus-bwjava

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/Cloud Services/SAP-BWJAVA/th-cloud-pus-bwjava-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |
| `agg/Cloud Services/SAP-BWJAVA/th-cloud-pus-bwjava-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/Cloud Services/SAP-BWJAVA/th-cloud-pus-bwjava-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |

##### th-cloud-pus-crm

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/Cloud Services/SAP-CRM/th-cloud-pus-crm-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/Cloud Services/SAP-CRM/th-cloud-pus-crm-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |

##### th-cloud-saplumira

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/th-cloud-saplumira/th-cloud-saplumira-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/th-cloud-saplumira/th-cloud-saplumira-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `agg/th-cloud-saplumira/th-cloud-saplumira-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### th-cloud-pus-s4

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/Cloud Services/SAP-S4/th-cloud-pus-s4-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |
| `agg/Cloud Services/SAP-S4/th-cloud-pus-s4-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `agg/Cloud Services/SAP-S4/th-cloud-pus-s4-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |

##### th-cloud-pus-slt

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `agg/Cloud Services/SAP-SLT/th-cloud-pus-slt-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |

---
