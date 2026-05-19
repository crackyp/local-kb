# Project Flywheel

Project Flywheel is a MarTech initiative to bring credit card transaction data into Adobe Experience Platform (AEP), enabling marketing teams to build audiences and journeys without routing every request through Data Engineering.

## Overview

Meridian National Bank currently builds marketing audiences in Snowflake and pushes them to AEP as pre-computed segment flags via nightly batch. This model worked for two years but is hitting its limits: every new audience requires a Data Eng ticket (2–3 week turnaround), and behavioral signals can't be acted on with useful latency. Greg's team has been waiting on a "spent $X at dining in the last 30 days" audience since January.

Flywheel aims to invert this: put transaction-level (or near-transaction-level) signal into AEP once, governed properly, and let marketing build audiences on top of it without new Data Eng tickets for each request.

## Key Tensions

The project threads through several unresolved tensions:

1. **Grain of data** — raw transactions vs. aggregated features
2. **Latency** — daily batch vs. near-real-time streaming
3. **Historical depth** — 13 months vs. 24 months
4. **Merchant normalization** — raw merchant strings now vs. wait for Merchant Taxonomy project
5. **Identity resolution** — join key to existing AEP profile
6. **Scope** — authorized only, include declined, refunds, disputes?
7. **Cost** — AEP ingestion is not free; forecasts range widely

## Timeline

- **March 2, 2026** — Project kickoff, #flywheel-kickoff channel created
- **March 5, 2026** — Kickoff email sent, initial scoping discussions
- **March 10, 2026** — Working session on use case definitions (MVP candidates confirmed)
- **March 17, 2026** — Target for PRD v1 draft and feature inventory
- **April 14, 2026** — Steerco review with Card LT (tentative)
- **Q3 2026** — Horizon card relaunch (time-boxed use case)

## Current State

- ~11M authorized transactions per day via TSYS → Snowflake nightly ETL
- End-to-end freshness: ~26–30 hours from authorization to audience in AEP
- 47 audience-related tickets filed Sept 2024–Feb 2026; 12 abandoned; median cycle time 23 days

## Related Topics

- [[Use-Cases]]
- [[Architecture]]
- [[Stakeholders]]
- [[Data-Governance]]

## Source Summary

*Source: [[raw/README.md]], [[raw/emails/01-kickoff-scoping.md]], [[raw/slack/03-channel-kickoff.md]], [[raw/prd/project-flywheel-prd-v1-draft.docx]], [[raw/slide-decks/current-state-architecture-deck.pptx]]*