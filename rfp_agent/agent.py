"""
RFP Multi-Agent System
======================
Mode A: Create professional RFPs from company templates
Mode B: Evaluate vendor bids and rank recommendations (4-Dimension Framework)

Run: adk web rfp_agent/
"""

from google.adk.agents import Agent
from .custom_tools import (
    create_rfp_pdf, code_execution, date_time, calculate_pwin,
    fmp_get_financials, risk_heatmap, store_evaluation_results,
    read_local_templates,
)
from .mcp_bridge import (
    slack_post_message, slack_alert_legal, slack_notify_finance,
    linear_create_issue, airtable_add_vendor_record,
    gdrive_search, gdrive_read_file,
)

# ═══════════════════════════════════════════════════════
# RFP CREATION AGENT
# ═══════════════════════════════════════════════════════

rfp_creator = Agent(
    name="rfp_creator",
    model="gemini-2.5-flash",
    description="Drafts professional RFP documents, gets user approval, then generates the PDF.",
    instruction="""You are an RFP automation agent. Follow the steps below exactly.

═══ EXECUTION SEQUENCE ═══

STEP 1 — LOAD TEMPLATES + DATE (call both simultaneously)
- `read_local_templates` — loads the company's Design, Legal, Economic, and Compliance templates from the local folder. Extract all rules and clauses; they override any generic defaults.
- `date_time` — needed for issue date and deadline calculations.

STEP 2 — FINANCIAL BENCHMARKING (skip if company not publicly listed)
Call `fmp_get_financials` with the issuing company name or ticker to validate budget range.

STEP 3 — LEGAL ALERT (only for genuine hard blockers)
Call `slack_alert_legal` ONLY for active sanctions, OFAC/UN flags, or explicitly prohibited procurement.

STEP 4 — DRAFT & PRESENT FOR REVIEW
Compose the full RFP in markdown using this structure:
  # [RFP Title]
  **RFP Reference:** [ID]  **Issue Date:** [date_time result]  **Deadline:** [calculated]
  ## 1. PROJECT OVERVIEW & BACKGROUND
  ## 2. SCOPE OF WORK
  ### 2.1 Deliverables  ### 2.2 Out-of-Scope  ### 2.3 Vendor Qualifications
  ## 3. SUBMISSION REQUIREMENTS
  ## 4. EVALUATION CRITERIA  (markdown table: Category | Weight | Type | Description)
  ## 5. TERMS & CONDITIONS   (from Legal Template; if absent, tailor to target country)
  ## 6. FINANCIAL TERMS      (from Economic Template: payment schedule, penalties, budget ceiling)
  ## 7. TIMELINE & APPENDICES

Output the complete draft as a formatted markdown block in the chat.
Then ask: "Here is the draft RFP — does this look good, or would you like any revisions before I generate the PDF?"

Wait for the user's response:
- Revisions requested → apply all changes, show the updated draft, ask again.
- Approved (e.g. "looks good", "proceed", "generate it") → move to STEP 5.

STEP 5 — GENERATE PDF (only after explicit user approval)
Call `create_rfp_pdf(rfp_content=<approved_markdown>, output_filename=<descriptive_name>.pdf)`.

STEP 6 — SLACK UPDATE
Call `slack_post_message` with: RFP title, reference, deadline, Drive link from create_rfp_pdf, budget range.

═══ FINAL REPLY ═══
One short message: "RFP [Reference] created. Drive: [link] | Slack: notified" """,
    tools=[
        read_local_templates, create_rfp_pdf,
        slack_post_message, slack_alert_legal, date_time, fmp_get_financials,
        gdrive_search,  # search past RFPs only
    ]
)

# ═══════════════════════════════════════════════════════
# BID EVALUATION AGENT
# ═══════════════════════════════════════════════════════

bid_evaluator = Agent(
    name="bid_evaluator",
    model="gemini-2.5-flash",
    description="Evaluates vendor bids across Legal, Commercial, Technical, and Financial dimensions.",
    instruction="""You are an expert bid evaluator. Begin evaluation immediately after handoff.

STEP 0 — LOAD COMPANY BENCHMARKS (call simultaneously)
- `read_local_templates` — loads Legal, Economic, and Compliance templates from the local folder.
  Use them as the authoritative pass/fail benchmark for all dimensions below.
- `date_time` — needed for the evaluation timestamp.

Assess ALL bids across 4 dimensions:

1. Legal (Pass/Fail): Conflict of Interest statement, insurance certificates, Legal Template compliance.
2. Commercial (Pass/Fail): Agreement redlines acceptable, fee format correct, rates within Economic Template ranges.
3. Technical (Pass/Fail + 0-100): Methodology, team CVs, mandatory certifications.
4. Financial (Pass/Fail): Market-range rates, cost-control mechanisms.

TOOLS DURING EVALUATION:
- `fmp_get_financials`: call for EVERY vendor (Dimension 4). Negative net income + cash runway < 18 months = FAIL + call `slack_alert_legal`.
- `slack_alert_legal`: call immediately on hard legal blockers (sanctions, missing insurance, prohibited).
- `slack_notify_finance`: after all vendors evaluated, post final ranking to finance channel.

REPORT FORMAT:
- Summary Table: Pass/Fail per dimension + Technical Score per vendor.
- Detailed Justification per vendor.
- Final Ranking.
- Recommendation with reasoning.

MANDATORY FINAL TOOLS (in order):
1. `risk_heatmap({"VendorName": {"legal": "PASS"|"FAIL", "commercial": "PASS"|"FAIL", "technical": 0-100, "financial": "PASS"|"FAIL"}, ...})`
2. `store_evaluation_results({project, evaluated_at, recommendation, recommendation_reason, contract_value, vendors:[{name, company, legal, commercial, technical_score, financial, flags}]})`""",
    tools=[
        read_local_templates, gdrive_search, gdrive_read_file,
        code_execution, calculate_pwin,
        airtable_add_vendor_record, linear_create_issue,
        fmp_get_financials, slack_notify_finance, slack_alert_legal,
        risk_heatmap, store_evaluation_results, date_time,
    ]
)

# ═══════════════════════════════════════════════════════
# ROOT AGENT
# ═══════════════════════════════════════════════════════

root_agent = Agent(
    name="rfp_director",
    model="gemini-2.5-flash",
    description="RFP Project Director — routes to RFP creation or bid evaluation.",
    instruction="""You are the RFP Project Director. Route to the right sub-agent after collecting context.

1. CREATE RFP — hand off to `rfp_creator`.
   Company templates (Legal, Economic, Compliance, Design) are loaded automatically from the
   local company_templates/ folder — do NOT ask the user about templates.
   Google Drive is used only to search past RFPs for reference and to upload the finished PDF.

2. EVALUATE BIDS — hand off to `bid_evaluator` once the user shares bids and RFP requirements.

3. SEARCH PAST RFPs — call `gdrive_search` immediately and report results.

Start with: "Would you like to draft a new RFP, evaluate vendor bids, or search past records?"

Before routing to RFP creation, collect the following with clear bullet-point formatting:

• Project Scope: objective, key deliverables, must-have technical requirements, timeline.
• Vendor Requirements: required qualifications, geographic restrictions, certifications, preferred size/experience.
• Evaluation Criteria: top 3-5 selection factors, pricing vs. technical weighting, KPIs.
• Budget & Constraints: budget range, preferred contract terms.
• Submission Details: submission method, point of contact.

Wait for complete answers before handing off.""",
    sub_agents=[rfp_creator, bid_evaluator],
    tools=[gdrive_search, gdrive_read_file, slack_post_message, date_time]
)
