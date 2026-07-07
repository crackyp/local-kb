# Databricks SQL Warehouses Guide

## Summary
This guide explains how to connect to, use, and manage SQL warehouses in Databricks on AWS. SQL warehouses are dedicated compute resources optimized for querying and exploring data. The guide covers the differences between serverless and pro/classic warehouses, procedures for starting and creating warehouses, permission requirements, and integrations with third-party BI tools and developer environments.

## Using SQL Warehouses
*   **Access:** Most users access SQL warehouses pre-configured by administrators. They appear in compute drop-down menus in the query editor, Catalog Explorer, and dashboards.
*   **Navigation:** View, sort, and search warehouses via the **SQL Warehouses** sidebar. They are sorted by state (running first), then alphabetically.
*   **Starter Warehouse:** Databricks automatically creates a small **Starter Warehouse** for new users, which can be edited or deleted.
*   **Notebook Integration:** Notebooks can be attached to pro or serverless SQL warehouses, though specific limitations apply.

## Serverless vs. Pro/Classic Warehouses
Databricks recommends using serverless SQL warehouses when available due to several key advantages:
*   **Instant and Elastic Compute:** Eliminates infrastructure wait times and over-provisioning. Intelligent workload management handles dynamic scaling during usage spikes.
*   **Minimal Management Overhead:** Databricks handles capacity management, patching, upgrades, and performance optimization, leading to predictable pricing.
*   **Lower Total Cost of Ownership (TCO):** Automatic provisioning and scaling reduce idle times and prevent over-provisioning.

## Starting and Creating Warehouses
### Starting a Warehouse
*   **Manual Start:** Click the start icon next to the warehouse in the sidebar. Requires at least `CAN MONITOR` permissions.
*   **Auto-Restart Conditions:** A stopped warehouse automatically restarts when:
    *   A query is run against it.
    *   A scheduled job assigned to it triggers.
    *   A JDBC/ODBC connection is established.
    *   An associated dashboard is opened.

### Creating a Warehouse
*   **Permissions:** Configuring and launching warehouses requires elevated administrator permissions.
*   **Data Access:** Unity Catalog governs data access permissions for most assets. Custom data access configurations can be applied instead of or alongside Unity Catalog.
*   **Troubleshooting:** Contact an administrator if you cannot connect to any warehouses, run queries due to a stopped warehouse, or access tables/data.

## Integrations and Developer Tools
### Third-Party BI Tools
Databricks SQL supports connections to various visualization and BI tools, including:
*   Power BI with Databricks
*   Tableau and Databricks

### Developer Tools
Developers can configure and run commands on SQL warehouses using:
*   Databricks SQL REST API
*   Databricks SQL Connector for Python
*   Databricks SQL CLI
*   Databricks Driver for SQLTools (Visual Studio Code)
*   DataGrip integration
*   DBeaver integration
*   SQL Workbench/J

## Terminology Note
*   **SQL Warehouses vs. SQL Endpoints:** Both terms refer to SQL-optimized compute resources powering Databricks SQL. In 2023, Databricks officially renamed "SQL endpoints" to "SQL warehouses."

## Related Concepts
*   [Databricks Onboarding and Governance Guide](databricks-onboarding-and-governance-guide.md)
*   [Databricks Data Steward Guide](databricks-data-steward-guide.md)
*   Unity Catalog
*   Serverless Compute Plane

---
Source: `databricks-official-documentation\docs.databricks.comawsencomputesql-warehouse.md`
Compiled: 2026-05-18T23:20:05.058573

---
Last updated from: `databricks-official-documentation\docs.databricks.comawsencomputesql-warehouse.md`
Compiled: 2026-05-27T15:57:54.367440
