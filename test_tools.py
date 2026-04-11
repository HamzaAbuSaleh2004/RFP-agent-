"""
Tool integration test — runs OUTSIDE the agent/LLM layer.
Each section makes exactly ONE API call to verify credentials + connectivity.

Run:  python test_tools.py
      python test_tools.py fmp slack firecrawl gdrive  # run specific sections only
"""

import sys
import asyncio
import os
from dotenv import load_dotenv

load_dotenv("rfp_agent/.env")

SECTIONS = sys.argv[1:] or ["local", "fmp", "firecrawl", "gdrive", "slack", "linear"]

PASS = "  PASS"
FAIL = "  FAIL"

def header(name):
    print(f"\n{'─'*50}\n  {name}\n{'─'*50}")

def check(label, result: str):
    ok = result and "ERROR" not in result[:20] and "Error" not in result[:20]
    print(f"{'✓' if ok else '✗'} {label}")
    if not ok or "--verbose" in sys.argv:
        # Print first 200 chars of result for context
        print(f"    → {str(result)[:200]}")
    return ok


# ═══════════════════════════════════════════════════════
# TIER 1 — Local stubs (zero cost, always run)
# ═══════════════════════════════════════════════════════

if "local" in SECTIONS:
    header("LOCAL STUBS (no API)")
    from rfp_agent.custom_tools import date_time, code_execution, calculate_pwin

    check("date_time()",        date_time())
    check("code_execution()",   code_execution("1+1"))
    check("calculate_pwin()",   str(calculate_pwin("{}")))


# ═══════════════════════════════════════════════════════
# TIER 2a — Financial Modeling Prep (1 call)
# ═══════════════════════════════════════════════════════

if "fmp" in SECTIONS:
    header("FMP — Financial Modeling Prep")
    from rfp_agent.custom_tools import fmp_get_financials

    # AAPL is always available, even on free tier
    result = fmp_get_financials("AAPL")
    check("fmp_get_financials('AAPL')", result)


# ═══════════════════════════════════════════════════════
# TIER 2b — Firecrawl (1 scrape of a tiny public page)
# ═══════════════════════════════════════════════════════

if "firecrawl" in SECTIONS:
    header("Firecrawl — web scrape")
    from rfp_agent.mcp_bridge import firecrawl_scrape

    # example.com is ~1 KB — minimal credit usage
    result = asyncio.run(firecrawl_scrape("https://example.com")) if asyncio.iscoroutinefunction(firecrawl_scrape) else firecrawl_scrape("https://example.com")
    check("firecrawl_scrape('example.com')", result)


# ═══════════════════════════════════════════════════════
# TIER 2c — Google Drive (search only, no upload)
# ═══════════════════════════════════════════════════════

if "gdrive" in SECTIONS:
    header("Google Drive")
    from rfp_agent.mcp_bridge import gdrive_search, gdrive_read_file

    result = gdrive_search("template")
    check("gdrive_search('template')", result)

    # Only read if search found something
    if "found" in result.lower() and "0 file" not in result:
        result2 = gdrive_read_file("Company Templet")
        check("gdrive_read_file('Company Templet')", result2)
    else:
        print("  ⚠ Skipping gdrive_read_file — no files found")


# ═══════════════════════════════════════════════════════
# TIER 2d — Slack (3 channels, 1 message each)
# ═══════════════════════════════════════════════════════

if "slack" in SECTIONS:
    header("Slack — channel routing")
    from rfp_agent.mcp_bridge import slack_post_message, slack_alert_legal, slack_notify_finance

    async def test_slack():
        r1 = await slack_post_message("[test] updates channel — tool test")
        check("slack_post_message → updates (C0ASMLBU3TK)", r1)

        r2 = await slack_alert_legal("[test] legal alert channel — tool test")
        check("slack_alert_legal  → legal   (C0ARWKER0G4)", r2)

        r3 = await slack_notify_finance("[test] finance channel — tool test")
        check("slack_notify_finance → finance (C0ASMA9B33J)", r3)

    asyncio.run(test_slack())


# ═══════════════════════════════════════════════════════
# TIER 2e — Linear (create one issue, costs nothing extra)
# ═══════════════════════════════════════════════════════

if "linear" in SECTIONS:
    header("Linear")
    from rfp_agent.mcp_bridge import linear_create_issue

    # Linear team IDs are workspace-specific — update TEAM_ID below if needed.
    # Find yours: Linear → Settings → Workspace → Teams → copy the team ID
    LINEAR_TEAM_ID = os.environ.get("LINEAR_TEAM_ID", "")
    if not LINEAR_TEAM_ID:
        print("  ⚠ Skipped — set LINEAR_TEAM_ID in .env or export it before running")
    else:
        async def test_linear():
            r = await linear_create_issue(
                title="[test] RFP tool connectivity check",
                description="Auto-created by test_tools.py — safe to delete.",
                team_id=LINEAR_TEAM_ID,
            )
            check("linear_create_issue", r)
        asyncio.run(test_linear())


print("\n" + "═"*50)
print("  Done. Add --verbose to see full output for all checks.")
print("═"*50 + "\n")
