# Meeting Notes: Flywheel Working Session — Use Case Definitions

**Date:** Tuesday, March 10, 2026 — 10:00–10:45 AM CT
**Location:** Google Meet (link in calendar invite)
**Facilitator:** Will Hendricks
**Note-taker:** Will Hendricks
**Attendees:**
- Will Hendricks (Sr. PM, MarTech Strategy)
- Priya Raman (Director, Credit Card Product)
- Greg Yamamoto (Sr. Manager, Card Rewards & Offers)
- Marcus Webb (Principal Data Engineer)
- Jessica Chen (Sr. Manager, Marketing Analytics)
- Rachel Okonkwo (Sr. Manager, Campaign Ops)

**Absent:** Ben Foster (pre-conflicted), Tom Bianchi (back-to-back), Linh Tran (conflicted)

---

## Pre-reads

- Will's kickoff email (March 5)
- Priya's top 6 blocked asks list (March 5)
- Marcus's current-state plumbing summary (March 6)

---

## Agenda

1. Recap of kickoff and working cadence
2. Walk the top 6 blocked asks — which map to Flywheel use cases
3. MVP scoping criteria — what gets us to a credible first cost estimate
4. Confirm working session rhythm

---

## Notes

### 1. Recap

**Will:** Summarized the kickoff email for the room. The goal of this working session is to take Priya's top 6 blocked asks and use them as forcing functions to define the MVP scope. Not to solve all of them for day one — to pick 2–3 we can build confidently and measure.

**Priya:** Clarified that the top 6 list is a representative sample, not an exhaustive backlog. The real number is larger but the top 6 capture the core pattern: behavioral signals we have in Snowflake but can't get to marketing in a useful form or timeframe.

**Marcus:** Noted that for this session we should focus on the marketing use cases, not the data engineering architecture. Architecture is a means to the use cases.

---

### 2. Walking the top 6 blocked asks

**Ask #1 — Category spend trigger (Greg, waiting since January):** Greg described the ask: cardholders who spent >$X at restaurants in the last 30 days → triggered offer in the monthly offers journey.

**Greg:** The current workaround is a Data Eng ticket that takes 2–3 weeks and produces an audience we can use once. If we want to change the threshold or the category, another ticket. We want to be able to iterate on the audience ourselves.

**Jessica:** Confirmed this is exactly the pattern AEP solves for. With event-level data in AEP, Analytics can build this audience in Journey Optimizer without a Data Eng cycle. The question is whether we ingest raw events or pre-computed features. Both can answer this use case.

**Consensus:** UC1 is viable. It maps to "category-based targeted offers" as a candidate.

---

**Ask #2 — Lapsed premium winback:** Priya described the use case: premium cardholders (Horizon, Reserve) whose spend has dropped 40%+ quarter over quarter → winback offer.

**Priya:** The logic is complex — we need to identify premium-tier customers, compute quarter-over-quarter spend delta, and flag the drop. She doesn't think this is in the existing feature table.

**Marcus:** Agreed. This requires either a new Snowflake feature or AEP event-level computation. He wants to flag this as a Phase 2 candidate unless Priya and Greg can simplify the definition.

**Priya:** If we can't do the 40% delta at MVP, can we do a simpler version? "Premium cardholder + no spend in 90 days" is closer to the dormancy use case.

**Consensus:** Simplified version (premium + 90-day dormancy) maps to UC2. The full QoQ delta logic is Phase 2.

---

**Ask #3 — Travel spend identification (Horizon card relaunch):** Product marketing wants to target classic cardholders with high travel spend for the Horizon relaunch.

**Priya:** This is time-boxed to the Q3 relaunch. If Flywheel misses the window, the use case becomes moot. She's reluctant to anchor MVP scope on a date we don't fully control.

**Greg:** Agreed. The relaunch window is firm — mid-September. If Flywheel is still in UAT in August, this use case gets dropped.

**Consensus:** Travel spend identification is a Phase 2 use case with a hard deadline. If Flywheel can be extended in time for Q3, we scope it then. Not in MVP.

---

**Ask #4 — Dormant card reactivation (90-day version):** Greg described the existing journey uses a 180-day dormancy trigger. He believes 90 days is better based on industry benchmarks.

**Greg:** Currently can't test this because the Data Eng ticket to change the dormancy logic is backlogged. The journey exists at 180 days — changing the threshold would require a new ticket and another 2–3 week cycle.

**Marcus:** This is the simplest use case on the list from a data standpoint. `days_since_last_purchase` exists in the current feature table. The only question is whether we can get the 90-day logic into AEP without building a new feature.

**Consensus:** UC2 is high confidence. Replace 180-day with 90-day dormancy trigger on existing journey. Simplest path to a measurable outcome.

---

**Ask #5 — Cross-sell to Horizon card from classic:** Card-to-card cross-sell. Spend signals that suggest a classic cardholder is outgrowing the product → upgrade offer.

**Priya:** This is inside the Card org, which makes it faster to scope than the HELOC case. But it still requires understanding what "outgrowing" means as a signal — spend category changes, ticket size increases, etc. Not a simple threshold.

**Jessica:** Analytics can build the audience logic once we know what the triggering signals are. The question is whether we have them today.

**Consensus:** Cross-sell is viable but requires definition work before MVP. Phase 2 candidate.

---

**Ask #6 — Dispute-in-flight marketing suppression:** Greg flagged this as a customer experience issue — reaching out to customers in the middle of a fraud investigation with a promotional offer is embarrassing and avoidable.

**Greg:** The signal is binary: is there an open dispute? The data lives in the Fraud & Disputes system, not the card authorization feed. A separate ingestion path would be needed.

**Rachel:** Important from Campaign Ops. Suppression signals need to be global — applicable to all marketing channels, not just card. If we build it for card only, we'll be building it again for Deposits in 6 months.

**Marcus:** Noted that the dispute feed is low volume (~3K events/day) and can be handled via a separate streaming path without reworking the main pipeline. This is feasible but not free.

**Consensus:** UC3 (dispute suppression) is viable. The binary nature makes it low-risk from a data standpoint. The 4-hour SLA Rachel mentioned needs to be validated with Fraud Ops before we commit.

---

### 3. MVP scoping criteria

**Will:** Proposed three criteria for what goes in MVP:
1. Data is available today (either in Snowflake or accessible without a multi-month ingestion project)
2. Marketing outcome is measurable (we can define baseline and target)
3. At least one named business owner who owns the outcome

**Applying criteria to the six asks:**

| Ask | Criterion 1 | Criterion 2 | Criterion 3 | MVP? |
|-----|-------------|-------------|-------------|------|
| Category offers (UC1) | Yes | Yes | Greg confirmed | Yes |
| Dormant reactivation (UC2) | Yes | Yes | Priya/Lifecycle confirmed | Yes |
| Dispute suppression (UC3) | Yes (separate feed needed) | Yes | Rachel confirmed | Yes |
| Lapsed premium (simplified) | Partial | Yes | Priya | Phase 2 |
| Travel/Horizon | Yes | Yes (but date risk) | Product Mktg | Phase 2 |
| Cross-sell | Partial | Partial | Card | Phase 2 |

---

### 4. Working session rhythm

**Will:** Proposed weekly 45-minute working sessions on Tuesdays at 10:00 CT, starting today. Shared Confluence space for artifacts. Will drive a PRD that iterates in the open rather than being delivered as a finished document.

**Priya:** Supported the cadence. Asked that any prep materials be distributed by Monday evening so she has time to review before the session.

**Marcus:** Asked that Data Eng items that require Tom's input be flagged at least 48 hours in advance.

**Rachel:** Requested that Campaign Ops be on the invite going forward.

---

## Decisions

1. MVP candidate use cases confirmed: UC1 (category offers), UC2 (dormant reactivation at 90 days), UC3 (dispute suppression)
2. Phase 2 candidates: lapsed premium, cross-sell, travel/Horizon (time-boxed)
3. Weekly working sessions confirmed: Tuesdays 10:00 CT
4. Pre-read distribution: Monday evening before each session
5. Tom Bianchi to be included on working sessions starting next week

---

## Action Items

| Action | Owner | Due |
|--------|-------|-----|
| Circulate finalized scope to wider stakeholder group | Will | March 12 |
| Confirm 4-hour SLA for dispute feed with Fraud Ops | Rachel | March 14 |
| Produce feature inventory: existing Snowflake features vs. MVP needs | Jessica + Ben | March 17 |
| Draft PRD v1 outline | Will | March 17 |
| Identify top-500 merchant volume list for normalization curation | Marcus | March 18 |
| Get Marcus the working session invite with 48-hr notice for Tom's items | Will | Ongoing |

---

**Meeting ended:** 10:47 AM CT
**Next meeting:** Tuesday March 17, 10:00 AM CT
**Doc status:** FINAL
