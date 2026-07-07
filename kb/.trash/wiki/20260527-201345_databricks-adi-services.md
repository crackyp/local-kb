# Databricks ADI Services Guide

## Summary
This guide outlines Databricks ADI Services, which provide access to hosted OpenAI and Gemini foundation models within the Azure Databricks environment. It details the available model versions, deprecation timelines for legacy Codex models, steps to enable the service, and the specific compliance terms and usage policies required for each model. Teams planning to integrate generative AI into their Databricks workflows should reference this guide alongside the [GSA Data Quality Assessment Handbook](gsa-data-quality-assessment-handbook.md) for AI readiness controls.

### What ADI Services Include
- Provides access to OpenAI and Gemini models via Databricks-hosted endpoints.
- Complements existing Azure Databricks Foundation Model APIs.
- Supports real-time and batch inference workloads using pay-per-token pricing.
- Enables advanced capabilities like Function Calling and Structured Output.
- Requires ADI Services eligibility and enablement before use.

### Deprecation Notice
- **Retirement Date:** July 16, 2026
- **Affected Models:** OpenAI GPT Codex models (GPT-5.2 Codex, GPT-5.1 Codex Max, GPT-5.1 Codex Mini)
- **Action Required:** Migrate to recommended replacement models before the retirement date. Refer to Databricks' retired models policy for migration guidance.

### Available Models
**OpenAI Models:**
- GPT-5.5 Pro, GPT-5.5
- GPT-5.4, GPT-5.4 mini, GPT-5.4 nano
- GPT-5.3 Codex
- GPT-5.2 Codex, GPT-5.2
- GPT-5.1, GPT-5.1 Codex Max, GPT-5.1 Codex Mini
- GPT-5, GPT-5-mini, GPT-5-nano

**Google Gemini Models:**
- Gemini 3.1 Pro (preview), Gemini 3.1 Flash Lite
- Gemini 3 Pro (preview), Gemini 3 Flash
- Gemini 2.5 Pro, Gemini 2.5 Flash

### How to Enable ADI Services
1. Navigate to the account settings on your Databricks workspace.
2. Locate and enable the **Integration with ADI Services** toggle.
3. Contact your Azure Databricks account team to confirm eligibility criteria and pricing details.

### Applicable Model Terms & Compliance
Users are responsible for ensuring compliance with all applicable model terms and use policies. Key requirements include:
- **OpenAI Models:** Subject to OpenAI high-risk use case mitigation requirements and usage policies.
- **Google Gemini Models:** Subject to Databricks Terms of Use for Google Models, Acceptable Use Policy, and Generative AI Prohibited Use Policy.
- *Note:* Always verify the latest terms before deploying models for production or public-facing AI use cases, as outlined in the [GSA Data Quality Assessment Handbook](gsa-data-quality-assessment-handbook.md).

### Related Concepts
- [Databricks Onboarding and Governance Guide](databricks-onboarding-and-governance-guide.md)
- [GSA Data Quality Assessment Handbook](gsa-data-quality-assessment-handbook.md)
- Foundation Model APIs
- Generative AI Risk Management
- Model Serving & Inference

---
Last updated from: `databricks-official-documentation\docs.databricks.comadi.md`
Compiled: 2026-05-27T15:42:59.708439
