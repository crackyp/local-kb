# Databricks Onboarding User Guide

## Summary
This guide provides GSA employees with step-by-step instructions for requesting Databricks access, understanding role-based permissions, navigating Unity Catalog, and adhering to data security best practices. It covers the onboarding checklist, access request workflows, role-specific tasks, medallion architecture, and initial workspace setup for both individual users and new organizational tenants.

## Introduction & Onboarding Checklist
Welcome to Databricks at GSA. This guide outlines how to obtain access, identify your appropriate role, and understand the high-level data management structure. For role-specific details, refer to the Additional Resources section. If you have questions, contact your Data Steward or see the Support section.

**Onboarding Checklist:**
- Request access to Databricks
- Confirm with your DEGB Lead that your team has completed the FCS Tenant Onboarding process (if applicable)
- Enroll in GSA Auth (if needed)
- Review the Rules of Behavior
- Gather request information (business justification, manager approval, role, catalog access)
- Submit your request for approval
- Complete Databricks training courses
- Review role-based user guides to confirm you can complete common tasks

## How to Request Access
*Note: This process is under review and may change. Check for updates.*

### Prepare Your Request
1. Confirm with your DEGB lead that your organization has completed the FCS Tenant Onboarding Process.
2. Enroll in GSA Auth if needed (see KB0033025 - GSA Auth Quick Start Enrollment Guide).
3. Review the EDS Rules of Behavior.
4. Gather the following information:
   - **Business Justification:** A brief description of how Databricks will help your job (e.g., "Need to analyze procurement trends for Q4 FY2025 report.").
   - **Manager Approval:** Required if applicable.
   - **Role Needed:** Determines accessible data tiers. You may hold multiple roles.
   - **Catalog Access Needed:** Consult your team lead or Data Steward if unsure.

### Submit Your Request
Email your Data Steward using the template below. Find your Data Steward on the Data Stewards List. If you lack a dedicated steward, contact your DEGB Lead.

**Request Email Template:**
```
To: [your-data-steward]@gsa.gov
Subject: Access Request - [Catalog Name]
Name: Your Name
Email: your.name@gsa.gov
Role Requested: Data Analyst (or Data Consumer, Data Engineer, AI/ML Engineer)
Catalog: [e.g., acquisition]
Schemas Needed: [e.g., silver, gold]
Business Justification: [Your justification]
Duration: Permanent (annual recertification)
Manager Approval: [Manager name and email] - Approved [date]
```

### Approval Timeline
- Wait 2-5 business days for feedback/approval.
- Your Data Steward will review your justification and contact you with questions.
- You will receive an email confirmation once approved and ready to log in.

## Understanding Roles & Data Tiers
Databricks uses a medallion architecture to organize data by quality and processing stage. Access is tiered based on your assigned role.

### Data Tiers (Medallion Architecture)
- **Gold (3rd Floor - Executive Suite):** Polished, final reports ready for business decisions. Accessible to everyone with Databricks access.
- **Silver (2nd Floor - Analysis Lab):** Cleaned, validated, and organized data ready for analysis. Accessible to Analysts and Engineers.
- **Bronze (1st Floor - Workshop):** Raw data straight from source systems, unprocessed. Accessible to Engineers only.

### Role Definitions & Permissions
- **Data Consumer:** Access to Gold tier data and published dashboards. Typical tasks: viewing reports, querying curated tables, exporting data.
- **Data Analyst:** Access to Silver and Gold tiers. Typical tasks: analyzing validated datasets, creating reports/visualizations, building SQL dashboards.
- **Data Engineer:** Access to Bronze, Silver, and Gold tiers with full CRUD permissions. Typical tasks: building ETL/ELT pipelines, managing tables, scheduling workflows.
- **AI/ML Engineer:** Access to Silver and Gold tiers. Typical tasks: training ML models, feature engineering, model deployment via MLflow.
- **Data Steward:** Full permissions on assigned catalogs. Typical tasks: reviewing access requests, granting/revoke permissions, maintaining metadata, monitoring data quality.

## Using Databricks
### Training & Glossary
- **Training:** Your account includes access to Databricks Academy. Complete the Databricks Fundamentals Learning Plan and role-specific training.
- **Key Terms:**
  - **Catalog:** Top-level collection of related databases/schemas.
  - **Schema:** Folder inside a catalog organizing related tables.
  - **Unity Catalog:** Security system controlling data access.
  - **OAuth/SSO:** Secure login via GSA SecureAuth/Okta.
  - **Service Principal:** Automated account for systems/jobs.
  - **CUI/PII:** Controlled Unclassified Information / Personally Identifiable Information.
  - **IEA:** Information Exchange Agreement for external data sharing.
  - **MLflow:** System for tracking/managing ML models.

### Workspaces & Catalogs
- **Workspaces:** Collaborative environments for managing data, notebooks, clusters, and models. Users may belong to multiple workspaces. Managed by a Workspace Owner. Not part of the `catalog.schema.table` namespace.
- **Catalogs:** Top-level organizational units containing schemas, tables, views, models, and volumes. Catalogs are bound to workspaces but are not exclusive to them. Data Products are highly organized, sharable catalogs.

### Common Tasks by Role
- **Query Data:** Use SQL Editor to browse tables (`SHOW TABLES IN catalog.schema;`), preview data (`SELECT * FROM catalog.schema.table LIMIT 100;`), and run aggregations.
- **Create Notebooks:** Navigate to Workspace → Create → Notebook. Select language (Python, SQL, Scala, R) and connect to a cluster.
- **Check Permissions:** Run `SHOW CATALOGS;`, `SHOW SCHEMAS IN catalog;`, and `SHOW GRANTS ON CATALOG catalog;` to verify access.
- **Find Data:** Use the Data Explorer sidebar, global search, or SQL queries (`SHOW TABLES IN catalog LIKE '*keyword*';`).

## Data & Security Best Practices
### Frequently Asked Questions
- **Personal Laptop Access:** Allowed only on GSA-managed devices.
- **Data Sharing/Downloads:** Never share via personal email, cloud storage, or unapproved USB drives. Classification dictates sharing rules.
- **Urgent Access:** Create a JIRA ticket marked "URGENT" with an executive sponsor and business impact. Temporary access (up to 7 days) may be granted pending a full review within 5 business days.
- **Password Sharing:** Strictly prohibited. Results in immediate revocation and potential administrative/legal action. Request individual access or share published reports instead.
- **Leaving a Project:** Notify supervisor and Data Steward within 24 hours. Submit a JIRA ticket for access revocation. Access is revoked same-day and audited monthly.
- **External Sharing:** Requires "Public" classification or explicit approval, Data Owner sign-off, Chief Privacy Officer approval (if PII), an IEA, and Delta Sharing configuration by a Workspace Admin.

### Security Guidelines
**DO:**
- Use individual accounts
- Lock screens when away
- Log out at end of day
- Report suspicious activity immediately
- Only access authorized data
- Complete annual security training
- Use GSA-managed devices

**DON'T:**
- Share passwords/credentials
- Leave sensitive data open on screens
- Email sensitive data without encryption
- Access via public WiFi without VPN
- Download data to personal devices
- Take screenshots of PII/CUI
- Attempt to access unauthorized data

## Accessing Databricks & Troubleshooting
### First Login
1. Navigate to the Databricks URL and sign in with SSO/Okta.
2. Authenticate with your GSA email and complete MFA.
3. Verify access to required catalogs, workspaces, and workflows.
4. Review role-based guides to confirm task completion.

### Troubleshooting
- **PERMISSION_DENIED:** Verify role assignment, check approval status, run `SHOW GRANTS ON CATALOG catalog_name;`, and contact your Data Steward.
- **Cluster Not Found:** Use the "Connect" dropdown to select an available cluster or create a new one if permitted.
- **Catalog Not Found:** Verify requested catalog, confirm provisioning with Data Steward, wait 5-10 minutes for sync, log out/in, and run `SHOW CATALOGS;`.

## Support & Additional Resources
- **Data Steward:** First point of contact for access requests, data quality, and catalog-specific help. See the Data Stewards List.
- **Workspace Admin:** Contact via FCS support channels for technical issues, cluster problems, or workspace configuration.
- **Data Governance Team:** Email `data.governance@gsa.gov` for policy, compliance, and training questions.
- **Documentation:** Quick Reference Guides, Architecture Diagrams, IaC Details, and Native Access Workflow Guides are available in the internal documentation repository.
- **Official Docs:** Databricks Official Docs, Unity Catalog Guide, SQL Reference, PySpark Documentation.

## FCS Tenant Onboarding (For New Organizations)
If your organization lacks a Databricks workspace, complete the FCS Tenant Onboarding process:
1. **Engage Cloud Advisory Team:** Initiate Cloud Smart Journey pathway and backlog provisioning.
2. **Complete Requirements Questionnaire:** Detail use cases, data sources, user counts, environment needs, compliance requirements, and network connections.
3. **Tenant Provisioning:** FCS Platform Team creates workspaces, sets up Unity Catalog structure, configures network/security, and provisions admin access. (Timeline: 2-4 weeks)
4. **Workspace Admin Onboarding:** Admins receive credentials and attend CETT orientation covering navigation, catalog structure, user management, data import, and security.

---
Last updated from: `Databricks-Onboarding-User-Guide-DRAFT.docx`
Compiled: 2026-05-18T09:11:29.958422
