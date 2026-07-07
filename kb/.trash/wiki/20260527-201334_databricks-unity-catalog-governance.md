# Databricks Unity Catalog Data Governance

## Summary
This page documents the official data governance framework provided by Unity Catalog within Databricks. It outlines how organizations can secure, discover, monitor, and share data assets using centralized governance tools. Key capabilities include hierarchical access control, AI-assisted discoverability, automated quality monitoring, secure collaboration features, and comprehensive auditing. This reference complements GSA-specific onboarding and stewardship procedures by detailing the underlying platform capabilities.

## Unity Catalog Governance Model
Unity Catalog serves as a centralized, open-source data catalog that provides governance for structured and unstructured data, as well as AI assets like machine learning models. Its core governance components include:
*   **Data Unification:** Provides a unified view of all data and AI assets across platforms to reduce duplication.
*   **Data Access Control:** Ensures data is accessible only to authorized users, groups, and service principals.
*   **Data Discoverability:** Enables users to easily locate and understand data assets.
*   **Data Quality:** Maintains accuracy, completeness, and consistency throughout the data lifecycle.
*   **Data Collaboration & Sharing:** Facilitates secure sharing within and across organizational boundaries.
*   **Auditing:** Tracks data usage and access patterns for compliance and security.

## Data Access Control
Unity Catalog enforces a hierarchical privilege model that manages access from the account level down to individual table rows and columns. Key access control mechanisms include:
*   **Manage Privileges:** Control access to securable objects (catalogs, schemas, tables, models) for users, groups, and service principals.
*   **Attribute-Based Access Control (ABAC):** Restrict access to data based on row-level attributes or column masks.
*   **Manage Identities:** Govern user and service principal identities within the Unity Catalog context.
*   **Fine-Grained Access Control:** Implement row filters and column masks to restrict visibility of sensitive data within tables.
*   **External Storage & Platforms:** Control access to cloud storage, external data platforms, and non-data services.
*   **External Platform Access:** Manage access for external platforms utilizing Apache Iceberg or open-source Unity Catalog APIs.

## Data Discoverability
Tools to help users find, understand, and trust data assets:
*   **Catalog Explorer:** Browse and search for data and AI assets using names, comments, and metadata tags.
*   **Catalog Browsers:** Integrated browsers within notebook and SQL query editors for direct asset navigation.
*   **AI-Generated Comments:** Automatically generate documentation for data and AI assets to improve context and discoverability.
*   **Table Insights:** View usage metrics in Catalog Explorer, including frequent users and common queries for any table.
*   **Data Lineage:** Capture and visualize data flows, transformations, and dependencies across the organization.
*   **Entity Relationship Diagrams (ERD):** Automatically display relationships between tables that have defined foreign keys.

## Data Quality Monitoring
Integrated tools to ensure data integrity and reliability:
*   **Data Quality Monitoring:** Monitor the quality of all assets in Unity Catalog using anomaly detection for catalogs/schemas and data profiling for individual tables.
*   **Certified and Deprecated System Tags (Private Preview):** Apply system tags to securable objects to indicate data quality levels or lifecycle status, enforcing governance and building trust in analytics and AI applications.

## Data Collaboration and Sharing
Unity Catalog enables secure data collaboration across workspaces, regions, organizations, and platforms:
*   **Delta Sharing:** A secure platform for sharing data and AI assets with external users, regardless of whether they use Databricks.
*   **Clean Rooms:** Managed environments allowing multiple participants (on Databricks or other platforms) to collaborate on projects without exposing underlying raw data.
*   **Databricks Marketplace:** An open forum for exchanging data and AI products, including a private data exchange for controlled sharing.

## Auditing
*   **Audit Logs:** Capture fine-grained details of dataset access and user actions.
*   **System Tables:** Provide a queryable interface to access and analyze account audit logs directly within Databricks.

## Legacy Governance Tools
Databricks recommends using Unity Catalog over these legacy features:
*   **Table Access Control:** A legacy model for programmatically granting/revoke access to objects in the workspace's built-in Hive metastore.
*   **IAM Role Credential Passthrough:** A legacy feature allowing automatic authentication to S3 buckets from clusters using the user's Databricks login identity.

## Related Concepts
*   [Databricks Onboarding and Governance Guide](databricks-onboarding-and-governance-guide.md)
*   [Databricks Data Steward Orientation Guide](databricks-data-steward-guide.md)
*   Unity Catalog
*   Delta Sharing
*   Data Lineage
*   Attribute-Based Access Control (ABAC)

---
Source: `docs.databricks.comawsendata-governance.md`
Compiled: 2026-05-18T23:19:47.581073

---
Last updated from: `databricks-official-documentation\docs.databricks.comawsendata-governance.md`
Compiled: 2026-05-27T16:08:02.155959
