---
name: rfp-agent-adk
description: >
  Build a multi-agent RFP system using Google ADK with two modes: (1) Create professional RFPs
  from company templates, and (2) Evaluate vendor bids to rank the best options. Includes creative
  agents for country-specific availability research, legal/regulatory compliance checking, and
  commercial compatibility analysis. Trigger on: RFP, request for proposal, bid evaluation,
  vendor ranking, procurement agent, RFP creation, proposal template, bid analysis, country
  compliance, legal compatibility, commercial feasibility, ADK multi-agent, or "build an RFP agent".
---

# RFP Multi-Agent System (ADK)

Two-mode system: **Create RFPs** following company templates + **Evaluate Bids** with intelligent ranking. Includes creative research agents for country-specific feasibility.

## PREREQUISITE: Google ADK Python Skill

This skill depends on the **Google ADK Python Skill** being installed. Always follow its patterns for imports and structure.

## ADK MANDATORY STRUCTURE

```
rfp_project/                    # Run adk commands from here
├── rfp_agent/                  # THE agent directory
│   ├── __init__.py             # MUST contain: from . import agent
│   ├── agent.py                # MUST define: root_agent = Agent(...)
│   ├── .env                    # GOOGLE_API_KEY=your-key
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── rfp_tools.py        # RFP document generation tools
│   │   ├── scoring_tools.py    # Bid scoring and ranking tools
│   │   └── research_tools.py   # Country/legal/commercial research
│   └── prompts/
│       ├── __init__.py
│       ├── creation.py         # RFP creation agent prompts
│       ├── evaluation.py       # Bid evaluation agent prompts
│       └── research.py         # Research agent prompts
├── templates/                  # Company RFP templates
│   └── default_rfp_template.md
├── pyproject.toml
└── README.md
```

**Iron rules:**
- `agent.py` exports `root_agent` — the ONLY entry point
- `__init__.py` contains `from . import agent` — nothing else
- All sub-agents are Python variables inside `agent.py` (or imported into it)
- Run: `adk web rfp_agent/` from `rfp_project/`

## The Two Modes

### Mode A: RFP Creator
User provides project requirements → system generates a professional RFP document following the company's template with proper sections, evaluation criteria, and legal terms.

### Mode B: Bid Evaluator
User uploads vendor bids/proposals → system analyzes each against RFP requirements, scores them on multiple dimensions, and produces a ranked recommendation report.

### Creative Research Agents (both modes)
- **Country Researcher**: Checks if requirements are feasible in the target country
- **Legal Compliance Agent**: Verifies regulatory compatibility (import/export, licenses, data laws)
- **Commercial Feasibility Agent**: Checks vendor availability, pricing norms, market maturity

## Reference Files

Read `references/agents-and-prompts.md` for all agent definitions with complete prompts.
Read `references/rfp-domain.md` for RFP structure and evaluation knowledge.

## Starter Code

Copy `assets/agent.py` → `rfp_agent/agent.py` for a working starting point.
Copy `assets/__init__.py` → `rfp_agent/__init__.py`.

## Build Order

1. Create project structure + copy starter files
2. Add `.env` with `GOOGLE_API_KEY`
3. Run `adk web rfp_agent/` → verify it starts
4. Implement tools in `tools/` as needed
5. Add company template in `templates/`
6. Test both modes
