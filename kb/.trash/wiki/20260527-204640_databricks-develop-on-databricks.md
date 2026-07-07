# Develop on Databricks

## Summary
This page outlines the tools, APIs, and workflows available for developers, data engineers, and data scientists to build, customize, and extend solutions on the Databricks platform. It covers workspace coding environments, local development integrations, infrastructure management, CI/CD pipelines, and community resources.

## Start Coding in the Workspace
Developing directly in the Databricks workspace is an efficient way to explore APIs and build initial solutions.
*   **Supported Languages:** Python, SQL, Scala, and R.
*   **Spark DataFrames:** Use Apache Spark DataFrames for data loading and transformation.
*   **REST API & SDKs:** Interact with Databricks objects via the REST API or install the Python SDK directly in a notebook.
*   **Databricks Utilities (`dbutils`):** Use built-in commands to manipulate files and interact with the workspace environment.

## Build Custom Apps and Solutions
Databricks supports both workspace-based and local development for creating secure, custom data and AI applications.
*   **Databricks Apps:** Build and share secure custom applications directly on the platform.
*   **IDE Extensions:** 
    *   **Visual Studio Code:** Official extension for workspace connection and resource management.
    *   **PyCharm:** Official JetBrains plugin for remote workspace configuration and cluster execution.
*   **SDKs:** Automate interactions using official SDKs for Python, Go, Java, and R.
*   **Authentication & Authorization:** Configure secure access for tools, scripts, and applications.

## Connect to Databricks
Various tools enable seamless connectivity between local development environments and Databricks resources.
*   **Databricks Connect:** Run code locally while executing on Databricks clusters via IDEs like PyCharm, IntelliJ IDEA, Eclipse, RStudio, and JupyterLab.
*   **Remote Development:** Connect your IDE to Databricks compute over an SSH tunnel.
*   **SQL Drivers and Tools:** Integrate Databricks SQL functionality into applications using drivers for Python, Go, JavaScript, and TypeScript.

## Manage Infrastructure and Resources
Developers can automate provisioning and resource management using industry-standard DevOps practices.
*   **Databricks CLI:** Command-line interface that wraps the REST API for local terminal or workspace web terminal usage.
*   **Declarative Automation Bundles:** Define and manage resources and CI/CD pipelines using the Databricks CLI.
*   **Terraform Provider:** Provision infrastructure and resources using Terraform.
*   **CI/CD Integration:** Connect with popular systems like GitHub Actions, Jenkins, and Apache Airflow.

## Collaborate and Share Code
Workspace features facilitate team collaboration and code reuse.
*   **User-Defined Functions (UDFs):** Develop and share reusable code across projects.
*   **Git Folders:** Version control and manage source code contributions directly within Databricks project files.

## Engage with the Developer Community
*   **Databricks MVPs:** Recognition program for community leaders and open-source contributors.
*   **Training:** Official learning modules for Apache Spark developers, Generative AI engineers, and Data Engineers.
*   **Community Forums:** Access knowledge bases and discussions via the Databricks and Apache Spark communities.

## Related Concepts
*   [Databricks Platform Overview and Documentation](databricks-platform-overview-and-documentation.md)
*   [Databricks Onboarding and Governance Guide](databricks-onboarding-and-governance-guide.md)
*   [Databricks Unity Catalog Overview](databricks-unity-catalog.md)

---
Last updated from: `databricks-official-documentation\docs.databricks.comawsendevelopers.md`
Compiled: 2026-05-27T20:36:55.127095
