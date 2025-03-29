# CCHBC

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
| [CCHBC-Governance-Center](#cchbc-governance-center) | 33.3% (3/9) | 42.1% (8/19) |
| [CCH SAFe Portfolio](#cch-safe-portfolio) | 3.0% (11/369) | 3.7% (30/817) |

---

## Project Details

### CCHBC-Governance-Center

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

### CCH SAFe Portfolio

#### Repository Overview

| Repository | Pipeline Adoption Rate |
|------------|-----------------|
| [detp-vmi-infrastructure](#detp-vmi-infrastructure) | 100.0% (3/3) |
| [dtso-ai-brainbank](#dtso-ai-brainbank) | 100.0% (3/3) |
| [tecs-cloud-cloudformation-terraform](#tecs-cloud-cloudformation-terraform) | 100.0% (3/3) |
| [tecs-cloud-itdcmint](#tecs-cloud-itdcmint) | 100.0% (3/3) |
| [tecs-cloud-ot-lz](#tecs-cloud-ot-lz) | 100.0% (3/3) |
| [tecs-cloud-sap-bw](#tecs-cloud-sap-bw) | 100.0% (3/3) |
| [tecs-cloud-sap-bwjava](#tecs-cloud-sap-bwjava) | 100.0% (3/3) |
| [tecs-cloud-sap-crm](#tecs-cloud-sap-crm) | 100.0% (2/2) |
| [tecs-cloud-saplumira](#tecs-cloud-saplumira) | 100.0% (3/3) |
| [tecs-cloud-sap-s4](#tecs-cloud-sap-s4) | 100.0% (3/3) |
| [tecs-cloud-sap-slt](#tecs-cloud-sap-slt) | 100.0% (1/1) |

#### Repository Details

##### detp-vmi-infrastructure

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `DETP/detp-vmi-infrastructure/detp-vmi-infrastructure-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `DETP/detp-vmi-infrastructure/detp-vmi-infrastructure-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `DETP/detp-vmi-infrastructure/detp-vmi-infrastructure-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### dtso-ai-brainbank

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `DTSO/dtso-ai-brainbank/dtso-ai-brainbank-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `DTSO/dtso-ai-brainbank/dtso-ai-brainbank-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `DTSO/dtso-ai-brainbank/dtso-ai-brainbank-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### tecs-cloud-cloudformation-terraform

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/tecs-cloud-cloudformation-terraform/tecs-cloud-cloudformation-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/tecs-cloud-cloudformation-terraform/tecs-cloud-cloudformation-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `TECS/tecs-cloud-cloudformation-terraform/tecs-cloud-cloudformation-terraform-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### tecs-cloud-itdcmint

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/tecs-cloud-itdcmint/tecs-cloud-itdcmint-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/tecs-cloud-itdcmint/tecs-cloud-itdcmint-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `TECS/tecs-cloud-itdcmint/tecs-cloud-itdcmint-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### tecs-cloud-ot-lz

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/Cloud Services/OT-LZ/tecs-cloud-ot-lz-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/Cloud Services/OT-LZ/tecs-cloud-ot-lz-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `TECS/Cloud Services/OT-LZ/tecs-cloud-ot-lz-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### tecs-cloud-sap-bw

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/Cloud Services/SAP-BW/tecs-cloud-sap-bw-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/Cloud Services/SAP-BW/tecs-cloud-sap-bw-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `TECS/Cloud Services/SAP-BW/tecs-cloud-sap-bw-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### tecs-cloud-sap-bwjava

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/Cloud Services/SAP-BWJAVA/tecs-cloud-sap-bwjava-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |
| `TECS/Cloud Services/SAP-BWJAVA/tecs-cloud-sap-bwjava-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/Cloud Services/SAP-BWJAVA/tecs-cloud-sap-bwjava-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |

##### tecs-cloud-sap-crm

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/Cloud Services/SAP-CRM/tecs-cloud-sap-crm-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/Cloud Services/SAP-CRM/tecs-cloud-sap-crm-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |

##### tecs-cloud-saplumira

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/tecs-cloud-saplumira/tecs-cloud-saplumira-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/tecs-cloud-saplumira/tecs-cloud-saplumira-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |
| `TECS/tecs-cloud-saplumira/tecs-cloud-saplumira-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |

##### tecs-cloud-sap-s4

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/Cloud Services/SAP-S4/tecs-cloud-sap-s4-generate-docs` | `pipeline-library/terraform/generate-docs.yaml` | extend |
| `TECS/Cloud Services/SAP-S4/tecs-cloud-sap-s4-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |
| `TECS/Cloud Services/SAP-S4/tecs-cloud-sap-s4-terraform-destroy` | `pipeline-library/terraform/destroy.yaml` | extend |

##### tecs-cloud-sap-slt

| Pipeline | Templates | Usage |
|----------|-----------|--------|
| `TECS/Cloud Services/SAP-SLT/tecs-cloud-sap-slt-terraform-deploy` | `pipeline-library/terraform/deploy.yaml` | extend |

---
