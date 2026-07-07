# Develop on Databricks

## Summary
This page outlines the tools, APIs, and environments available for developers building solutions on the Databricks platform. It covers workspace coding, local development with IDEs, SDKs, CLI and infrastructure management, CI/CD integration, code collaboration features, and community resources.

### Start Coding in the Workspace
Developing directly in the workspace is ideal for quickly getting familiar with Databricks APIs. The platform supports Python, SQL, Scala, R, and other developer-focused features.
*   **Language Support:** Tutorials and overviews are available for Python, Scala, and R. See the [Languages overview](https://docs.databricks.com/aws/en/languages/) for supported tools.
*   **SQL & Spark:** Browse the [SQL language reference](https://docs.databricks.com/aws/en/sql/language-manual/) and work through the [Apache Spark DataFrames tutorial](https://docs.databricks.com/aws/en/learn/python/load-transform-data/) or [PySpark basics](https://docs.databricks.com/aws/en/learn/python/pyspark-basics/).
*   **Utilities & SDKs:** Install the [Python SDK](https://docs.databricks.com/aws/en/dev-tools/python-sdk/) in a notebook, explore the [REST API reference](https://docs.databricks.com/aws/en/api/workspace), and use `dbutils` commands to manipulate files and the Databricks environment.

### Build Custom Apps and Solutions
Databricks supports both workspace and local development. Workspace development offers UI-based app creation, Unity Catalog volumes, Genie Code debugging, and Git folders. Local development via an IDE supports a wider range of languages, advanced debugging, test frameworks, and direct source control.
*   **Databricks Apps:** Create secure, shareable data and AI custom applications on the platform.
*   **VS Code Extension:** Connect to remote workspaces for easy configuration and a UI for managing resources.
*   **PyCharm Plugin:** Configure remote workspace connections and run files on clusters (developed by JetBrains in partnership with Databricks).
*   **Databricks SDKs:** Automate interactions using SDKs instead of direct REST API calls. Available for [Python](https://docs.databricks.com/aws/en/dev-tools/python-sdk/), [Go](https://docs.databricks.com/aws/en/dev-tools/go-sdk/), [Java](https://docs.databricks.com/aws/en/dev-tools/java-sdk/), and [R](https://docs.databricks.com/aws/en/dev-tools/r-sdk/).

### Connect to Databricks
Various tools enable developers to connect their environments and processes to Databricks workspaces and resources.
*   **Databricks Connect:** Connect popular IDEs (PyCharm, IntelliJ IDEA, Eclipse, RStudio, JupyterLab) to Databricks.
*   **Remote Development:** Connect your IDE to Databricks compute over an SSH tunnel.
*   **SQL Drivers and Tools:** Run SQL commands/scripts, interact programmatically, and integrate SQL functionality into applications written in Python, Go, JavaScript, and TypeScript.
*   **Third-Party Integrations:** Many additional tools can connect to clusters and SQL warehouses. See [Technology partners](https://docs.databricks.com/aws/en/integrations/).

### Manage Infrastructure and Resources
Developers and data engineers can automate provisioning and management using industry-standard tools, supporting both simple and complex CI/CD pipelines.
*   **Databricks CLI:** Access Databricks functionality via command line. Wraps the REST API for use in local terminals or the workspace web terminal.
*   **Declarative Automation Bundles:** Define and manage resources and CI/CD pipelines using best practices for data/AI projects (a feature of the CLI).
*   **Terraform Provider:** Provision Databricks infrastructure and resources using Terraform.
*   **CI/CD Tools:** Integrate with popular systems like GitHub Actions, Jenkins, and Apache Airflow.

### Collaborate and Share Code
The workspace includes built-in features to support developer collaboration and code reuse.
*   **UDFs:** Develop user-defined functions to reuse and share code across projects.
*   **Git Folders:** Configure Git folders to version control and manage contributions to Databricks project files.

### Engage with the Developer Community
Databricks maintains an active developer ecosystem supported by several programs:
*   **Databricks MVPs:** Recognizes community members, data scientists, engineers, and open-source enthusiasts who contribute significantly to the data/AI community.
*   **Training:** Official learning modules for Apache Spark developers, Generative AI engineers, Data engineers, and more.
*   **Community Forums:** Access knowledge bases and discussions via the [Databricks community](https://community.databricks.com/) and [Apache Spark community](https://community.apache.org/spark.html).

## Related Concepts
*   [Databricks Platform Overview and Documentation](databricks-platform-overview-and-documentation.md)
*   [Databricks Onboarding and Governance Guide](databricks-onboarding-and-governance-guide.md)
*   Local Development Tools
*   CI/CD Pipelines
*   Databricks SDKs

---
Last updated from: `databricks-official-documentation\docs.databricks.comawsendevelopers.md`
Compiled: 2026-05-27T20:36:33.336092
