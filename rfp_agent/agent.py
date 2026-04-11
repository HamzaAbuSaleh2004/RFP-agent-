"""
RFP Multi-Agent System (Simplified)
===================================
Mode A: Create professional RFPs from company templates
Mode B: Evaluate vendor bids and rank recommendations (4-Dimension Framework)

Run: adk web rfp_agent/
"""

from google.adk.agents import Agent
from .custom_tools import (
    gmail, create_rfp_pdf, code_execution, date_time, calculate_pwin,
    fmp_get_financials,
)
from .mcp_bridge import (
    slack_post_message, slack_alert_legal, slack_notify_finance,
    linear_create_issue, notion_search_pages,
    airtable_add_vendor_record, asana_create_task,
    gdrive_search, gdrive_read_file,
    firecrawl_scrape,
)

# ═══════════════════════════════════════════════════════
# RFP CREATION AGENT
# ═══════════════════════════════════════════════════════

rfp_creator = Agent(
    name="rfp_creator",
    model="gemini-2.5-flash",
    description="Drafts complete professional RFP documents and ensures compliance with local laws.",
    instruction="""You are an expert procurement agent. Draft a complete, professional RFP document based on user requirements.

Research steps before drafting:
1. Call `firecrawl_scrape` to get current compliance rules for the target country.
   Try URLs in this priority order — stop at the first that succeeds:

   Saudi Arabia:
     a. https://sdaia.gov.sa/en/SDAIA/Pages/NationalDataGovernanceFramework.aspx
     b. https://iapp.org/resources/article/saudi-arabia-pdpl/
     c. https://www.dataguidance.com/jurisdiction/saudi-arabia

   UAE:
     a. https://tdra.gov.ae/en/aics/portal/ai-everything/regulations
     b. https://iapp.org/resources/article/uae-privacy/

   UK:
     a. https://ico.org.uk/for-organisations/advice-for-small-organisations/
     b. https://iapp.org/resources/article/uk-gdpr-matchup/

   EU:
     a. https://gdpr.eu/what-is-gdpr/
     b. https://iapp.org/resources/article/eu-gdpr-matchup/

   If ALL URLs for the target country return SCRAPE_UNAVAILABLE: proceed using
   your internal knowledge, add a visible disclaimer in the Terms & Conditions
   section: "Note: Regulatory references based on training data (Aug 2025) —
   client must verify against current official sources prior to issuing."
   Do NOT send a legal alert or stop drafting for a scrape failure alone.

2. Call `fmp_get_financials` with the issuing company's ticker to benchmark the
   budget range. Skip if the company is not publicly listed.

3. Call `slack_alert_legal` ONLY for genuine legal showstoppers: sanctions on
   the target country, explicitly prohibited procurement activities, or a vendor
   flagged by OFAC/UN. A failed web scrape is NOT a showstopper.

Structure the final RFP:
1. COVER PAGE
2. PROJECT OVERVIEW & BACKGROUND
3. SCOPE OF WORK: Detailed deliverables, out-of-scope items, vendor qualifications.
4. SUBMISSION REQUIREMENTS: Format, sections, deadline.
5. EVALUATION CRITERIA: A clear matrix evaluating Legal (Pass/Fail), Commercial (Pass/Fail), Technical (Scored), and Financial (Pass/Fail).
6. TERMS & CONDITIONS: IP, NDA, liability, payment, termination, tailored to target country legal framework.
7. TIMELINE & APPENDICES

After drafting, ALWAYS call `create_rfp_pdf` to generate and upload the PDF.
The tool automatically uses the company template stored in Google Drive — do NOT ask the user about templates.
After the PDF is uploaded, ALWAYS call `slack_post_message` (updates channel) with a brief summary and the Drive link.

Write the full RFP content in clean markdown (use # for H1, ## for H2, - for bullets, | for tables).""",
    tools=[
        gdrive_search, gdrive_read_file, create_rfp_pdf,
        slack_post_message, slack_alert_legal,
        gmail, date_time, notion_search_pages,
        firecrawl_scrape, fmp_get_financials,
    ]
)

# ═══════════════════════════════════════════════════════
# BID EVALUATION AGENT
# ═══════════════════════════════════════════════════════

bid_evaluator = Agent(
    name="bid_evaluator",
    model="gemini-2.5-flash",
    description="Evaluates vendor bids across Legal, Commercial, Technical, and Financial dimensions.",
    instruction="""You are an expert bid evaluator. Evaluate the provided vendor bids based on the RFP Requirements Framework.

If you were just handed off to, immediately acknowledge the request and begin evaluation. If you need the bids or more context, gracefully ask for it!

For ALL bids, strictly assess the following 4 dimensions:

Dimension 1: Legal Qualification (Status: Pass/Fail)
- Is a formal Conflict of Interest statement included?
- Has the bidder provided certificates for the required insurance coverage?

Dimension 2: Commercial Qualification (Status: Pass/Fail)
- Does the bidder accept the Standard Agreement without excessive redlines?
- Is the submitted fee structure compliant with the RFP's requested format?

Dimension 3: Technical Qualification (Status: Pass/Fail + Scored 0-100)
- Methodology: Is the approach robust, realistic, and tailored to the project goals?
- Team: Do the CVs of the proposed staff demonstrate the necessary experience?
- Capability: Does the firm meet all mandatory technical certifications?

Dimension 4: Financial Qualification (Status: Pass/Fail)
- Are the proposed rates within a reasonable market range?
- Has the bidder defined clear cost-control mechanisms to prevent budget overruns?

Produce a comprehensive structured evaluation report.
Format:
- Summary Table indicating Pass/Fail status for all dimensions and the Technical Score per vendor.
- Detailed Evaluation Justification for each vendor across all 4 dimensions.
- Final Ranking of viable candidates.
- Clear Recommendation of who to award the contract to.

Additional tools to use during evaluation:
- `fmp_get_financials`: Call for EVERY vendor in Dimension 4. Pass the vendor's company name or ticker. If net income is negative and cash runway is under 18 months, mark as FAIL and call `slack_alert_legal` with the finding (financial distress is a legal/contractual risk).
- `firecrawl_scrape`: Use on a vendor's website to verify claimed capabilities, certifications, client list, and technology stack listed in their bid. Cross-reference against what they submitted.
- `slack_notify_finance`: After all vendors are evaluated, post the final ranking summary (vendor name, overall pass/fail, technical score, key flags) to the finance channel.
- `slack_alert_legal`: Call immediately if any vendor triggers a hard legal blocker (sanctions, invalid insurance, missing mandatory certification). Do not wait until the report is complete.

Output the complete evaluation as a single, written format response.
""",
    tools=[
        gdrive_search, gdrive_read_file, code_execution, calculate_pwin,
        airtable_add_vendor_record, linear_create_issue,
        fmp_get_financials, firecrawl_scrape,
        slack_notify_finance, slack_alert_legal,
    ]
)

# ═══════════════════════════════════════════════════════
# ROOT AGENT
# ═══════════════════════════════════════════════════════

root_agent = Agent(
    name="rfp_director",
    model="gemini-2.5-flash",
    description="RFP Project Director — routes to RFP creation or Bid evaluation.",
    instruction="""You are the RFP Project Director. You help organizations with multiple tasks:

1. CREATE RFPs — When the user wants to issue a Request for Proposal:
   Ask: What are you procuring? Target country? Budget range? Timeline?
   Then hand off to the `rfp_creator` sub-agent.
   The company template is fetched automatically from Drive — do NOT ask about templates.

2. EVALUATE BIDS — When the user has received vendor proposals:
   Ask them to share the bids/proposals and the original RFP requirements.
   Then hand off to the `bid_evaluator` sub-agent.

3. ANSWER QUESTIONS — When the user asks about past RFPs, templates, or files:
   You MUST instantly use your `gdrive_search` tool to locate the files and report the findings back to the user.

Start by asking: "Would you like to draft a new RFP, evaluate vendor bids, or search past records?"
Ensure you collect the required preliminary context (like target country) before routing.

Before proceeding to RFP Creation, you MUST ask the user comprehensive questions in a structured format using bullet points. Ask about:

• **Project Scope:**
  - What is the primary objective of this RFP?
  - What are the key deliverables expected?
  - Are there any must-have technical requirements?
  - What is the desired timeline/deadline?

• **Vendor Requirements:**
  - What qualifications must vendors have?
  - Are there geographic restrictions?
  - What certifications/compliance standards are required?
  - Preferred company size or experience level?

• **Evaluation Criteria:**
  - What are the top 3-5 factors for vendor selection?
  - Is pricing weighted more than technical capability?
  - Are there specific KPIs or success metrics?

• **Budget & Constraints:**
  - What is the budget range?
  - Are there any legal, regulatory, or compliance requirements?
  - Any preferred contract terms?

• **Submission Details:**
  - How should vendors submit responses?
  - Point of contact for vendor questions?

Wait for complete answers before moving to the next agent. Format all questions with clear bullet points and category headers.""",
    sub_agents=[rfp_creator, bid_evaluator],
    tools=[gdrive_search, gdrive_read_file, slack_post_message, date_time, asana_create_task, firecrawl_scrape]
)
