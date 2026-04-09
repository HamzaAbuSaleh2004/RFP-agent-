"""
RFP Multi-Agent System
======================
Mode A: Create professional RFPs from company templates
Mode B: Evaluate vendor bids and rank recommendations
+ Creative research agents for country/legal/commercial feasibility

Run: adk web rfp_agent/
"""

from google.adk.agents import Agent, SequentialAgent, ParallelAgent
from google.adk.tools import google_search


# ═══════════════════════════════════════════════════════
# RESEARCH AGENTS (shared by both modes)
# ═══════════════════════════════════════════════════════

country_researcher = Agent(
    name="country_researcher",
    model="gemini-2.5-flash",
    description="Researches country-specific availability, infrastructure, trade, and cultural factors",
    instruction="""Research whether the procurement requirements are feasible
in the specified target country/region.

Investigate:
1. AVAILABILITY: Are required products/services available locally?
   Local suppliers vs import needs, supply chain reliability, lead times.
2. INFRASTRUCTURE: Technology, workforce, language considerations.
3. TRADE: Tariffs, trade agreements, sanctions, currency issues.
4. CULTURAL: Business practices, procurement timelines, holidays.

Output a feasibility assessment with GO / CAUTION / STOP rating per area.
Use google_search to find current information.""",
    tools=[google_search],
    output_key="research:country_report",
)

legal_compliance_agent = Agent(
    name="legal_compliance_agent",
    model="gemini-2.5-flash",
    description="Checks legal and regulatory compatibility for procurement in target country",
    instruction="""Check legal and regulatory compatibility for this procurement
in the target country.

Research:
1. DATA PROTECTION: GDPR, CCPA, PDPA, or local equivalents. Data residency rules.
2. INDUSTRY REGULATIONS: Licenses, certifications (ISO, SOC2), government approvals.
3. LABOR LAWS: Contractor classification, working hours, benefits.
4. ENVIRONMENTAL: Compliance requirements, sustainability reporting.
5. ANTI-CORRUPTION: FCPA, UK Bribery Act, local anti-corruption laws.

Rate each: COMPLIANT / NEEDS ATTENTION / RISK.
Flag any showstoppers. Use google_search for accuracy.""",
    tools=[google_search],
    output_key="research:legal_compliance",
)

commercial_feasibility_agent = Agent(
    name="commercial_feasibility_agent",
    model="gemini-2.5-flash",
    description="Assesses market conditions, pricing benchmarks, and vendor landscape",
    instruction="""Assess commercial feasibility for this procurement in the target country.

Research:
1. MARKET MATURITY: Number of vendors, market leaders, alternatives.
2. PRICING BENCHMARKS: Typical ranges, regional cost comparison.
3. VENDOR LANDSCAPE: Top vendors, local vs international mix.
4. COMMERCIAL RISKS: Payment infrastructure, contract enforcement, stability.
5. SUSTAINABILITY: Long-term vendor viability, support availability.

Rate overall: HIGH / MEDIUM / LOW feasibility.
Use google_search for current market data.""",
    tools=[google_search],
    output_key="research:commercial_feasibility",
)

research_team = ParallelAgent(
    name="research_team",
    sub_agents=[country_researcher, legal_compliance_agent, commercial_feasibility_agent],
    description="Runs country, legal, and commercial research in parallel",
)


# ═══════════════════════════════════════════════════════
# RFP CREATION AGENTS
# ═══════════════════════════════════════════════════════

scope_agent = Agent(
    name="scope_agent",
    model="gemini-2.5-flash",
    description="Drafts scope of work from user requirements",
    instruction="""Draft the Scope of Work for an RFP.

Produce:
1. PROJECT OVERVIEW: What's being procured and why (2-3 paragraphs)
2. OBJECTIVES: Numbered, measurable objectives
3. SCOPE OF WORK: Detailed deliverables with acceptance criteria, timeline, standards
4. OUT OF SCOPE: What is NOT included
5. VENDOR QUALIFICATIONS: Minimum experience, certifications, capacity

Use "shall" for mandatory, "should" for desirable, "may" for optional.
Be specific enough to evaluate but not so prescriptive as to block innovation.""",
    output_key="creation:scope",
)

criteria_agent = Agent(
    name="criteria_agent",
    model="gemini-2.5-flash",
    description="Designs evaluation criteria and scoring rubric",
    instruction="""Design evaluation criteria for this RFP.

Create a weighted scoring table:
- Technical Approach: 35%
- Past Performance: 20%
- Key Personnel: 15%
- Cost/Price: 20%
- Innovation: 10%

Adjust weights by procurement type (tech → more technical, consulting → more personnel).
Define what scores 5, 3, and 1 for each criterion.
Include pass/fail mandatory requirements that gate entry before scoring.""",
    output_key="creation:criteria",
)

legal_terms_agent = Agent(
    name="legal_terms_agent",
    model="gemini-2.5-flash",
    description="Adds legal and commercial terms appropriate for the target country",
    instruction="""Add legal and commercial terms to the RFP.

Include: IP ownership, confidentiality/NDA, liability limits, payment terms,
termination clauses, dispute resolution, compliance requirements, insurance minimums,
warranty terms.

Tailor to the target country's legal framework.
Incorporate findings from legal compliance research if available:
{research:legal_compliance?}

Flag terms needing legal counsel review.""",
    output_key="creation:legal_terms",
)

template_formatter = Agent(
    name="template_formatter",
    model="gemini-2.5-flash",
    description="Assembles all sections into a complete professional RFP document",
    instruction="""Assemble a complete, professional RFP document.

Structure:
1. COVER PAGE: Company name, RFP title, number, dates
2. TABLE OF CONTENTS
3. INTRODUCTION & PURPOSE
4. ORGANIZATIONAL BACKGROUND
5. SCOPE OF WORK: {creation:scope?}
6. SUBMISSION REQUIREMENTS: Format, sections, deadline
7. EVALUATION CRITERIA: {creation:criteria?}
8. TERMS & CONDITIONS: {creation:legal_terms?}
9. TIMELINE: Issue → Q&A → Due → Evaluation → Award
10. CONTACT INFORMATION
11. APPENDICES: Requirements matrix, pricing template, forms

Integrate research findings where relevant:
- Country report: {research:country_report?}
- Legal compliance: {research:legal_compliance?}
- Commercial feasibility: {research:commercial_feasibility?}

Add notes about country-specific requirements in relevant sections.
Output the complete RFP as a well-formatted document.""",
    output_key="creation:final_rfp",
)

rfp_creation_team = SequentialAgent(
    name="rfp_creation_team",
    sub_agents=[scope_agent, criteria_agent, legal_terms_agent, research_team, template_formatter],
    description="Creates a complete professional RFP: scope → criteria → legal → research → format",
)


# ═══════════════════════════════════════════════════════
# BID EVALUATION AGENTS
# ═══════════════════════════════════════════════════════

bid_parser_agent = Agent(
    name="bid_parser_agent",
    model="gemini-2.5-flash",
    description="Extracts structured information from vendor bids",
    instruction="""Parse vendor bids and extract structured information.

For each bid extract:
- Vendor name and contact
- Executive summary of approach
- Proposed solution details
- Team/personnel
- Timeline and milestones
- Pricing breakdown
- References and past performance
- Certifications
- Deviations from RFP requirements
- Value-adds offered

Output structured data per vendor.""",
    output_key="evaluation:parsed_bids",
)

compliance_checker = Agent(
    name="compliance_checker",
    model="gemini-2.5-flash",
    description="Checks if each bid meets all mandatory requirements",
    instruction="""Check each vendor bid against mandatory requirements.

For every mandatory requirement:
- PASS: Vendor explicitly addresses it
- FAIL: Vendor ignores or takes exception
- UNCLEAR: Needs clarification

ANY failed mandatory requirement = disqualified.
Also check: submitted on time, correct format, all forms included, within page limits.
Produce a compliance matrix per vendor.""",
    output_key="evaluation:compliance_results",
)

technical_scorer = Agent(
    name="technical_scorer",
    model="gemini-2.5-flash",
    description="Scores technical approach quality for each vendor",
    instruction="""Score each compliant vendor's technical approach (1-5 per criterion).

Apply evaluation criteria weights. For each criterion:
- Score with written justification
- Compare approaches across vendors
- Note strengths and weaknesses
- Flag technical risks

Show weighted score calculations.""",
    output_key="evaluation:technical_scores",
)

commercial_scorer = Agent(
    name="commercial_scorer",
    model="gemini-2.5-flash",
    description="Scores pricing and commercial terms for each vendor",
    instruction="""Score vendor pricing and commercial terms (1-5 each).

Analyze: total cost comparison, cost breakdown reasonableness, hidden costs,
payment terms, price-to-value ratio, cost risks (fixed vs variable).

Flag unrealistically low pricing (change order risk) or poor value.""",
    output_key="evaluation:commercial_scores",
)

ranking_agent = Agent(
    name="ranking_agent",
    model="gemini-2.5-flash",
    description="Produces final vendor ranking with recommendation report",
    instruction="""Produce the final vendor ranking and recommendation.

Combine all scores into a ranking table:
| Rank | Vendor | Technical | Commercial | Research | Total | Recommendation |

For the top vendor: why recommended, strengths, risks, negotiation points.
For runner-ups: why lower, conditions where they'd be preferred.
For disqualified vendors: reason for disqualification.

Incorporate research findings:
- Country report: {research:country_report?}
- Legal compliance: {research:legal_compliance?}
- Commercial feasibility: {research:commercial_feasibility?}

Add a "Research Risk Adjustment" that boosts or penalizes vendors based on
their ability to operate in the target country.""",
    output_key="evaluation:final_ranking",
)

bid_evaluation_team = SequentialAgent(
    name="bid_evaluation_team",
    sub_agents=[bid_parser_agent, compliance_checker, technical_scorer,
                commercial_scorer, research_team, ranking_agent],
    description="Evaluates bids: parse → compliance → score → research → rank",
)


# ═══════════════════════════════════════════════════════
# ROOT AGENT
# ═══════════════════════════════════════════════════════

root_agent = Agent(
    name="rfp_director",
    model="gemini-2.5-flash",
    description="RFP Project Director — creates RFPs and evaluates vendor bids",
    instruction="""You are the RFP Project Director. You help organizations with two tasks:

1. CREATE RFPs — When the user wants to issue a Request for Proposal:
   Ask: What are you procuring? Target country? Budget range? Timeline?
   Then transfer to rfp_creation_team.

2. EVALUATE BIDS — When the user has received vendor proposals:
   Ask them to share the bids/proposals and the original RFP requirements.
   Then transfer to bid_evaluation_team.

Both modes include automatic research into country availability,
legal compliance, and commercial feasibility for the target region.

Start by asking: "Would you like to create a new RFP or evaluate vendor bids?"

Always gather:
- Target country/region (needed for compliance checks)
- Industry/sector
- Key requirements or priorities""",
    sub_agents=[rfp_creation_team, bid_evaluation_team],
)
