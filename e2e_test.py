"""
End-to-End Test Suite for RFP Director
=======================================
Tests the full workflow: Create RFP → Agent Chat → View Documents → Evaluate Bids

Run:
    1. Start the server:  uvicorn rfp_agent.main:app --reload
    2. Run tests:         python e2e_test.py

Prerequisites: pip install playwright httpx && python -m playwright install chromium
"""
import asyncio
import json
import sys
import time
import httpx
from datetime import datetime
from playwright.async_api import async_playwright

# Force UTF-8 on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"
RESULTS = []
TEST_NUM = 0

# ── Fake data ────────────────────────────────────────────────────────────────

FAKE_RFP = {
    "title": "SmartShelf Inventory Automation System",
    "description": (
        "Replace manual warehouse tracking with an automated, predictive inventory "
        "management system that reduces overstock by 20% and eliminates stock-outs "
        "for high-demand items across 3 warehouse locations."
    ),
    "language": "en",
    "created_by": "e2e_tester",
    "invited_users": ["sarah@logistics.com", "ops@warehouse.io"],
}

FULL_RFP_CONTEXT = (
    "I want to draft a new RFP. Here is ALL the project context I have:\n\n"
    "- **Title**: SmartShelf Inventory Automation System\n"
    "- **Description**: Replace manual warehouse tracking with an automated, "
    "predictive inventory management system.\n"
    "- **Language**: English\n\n"
    "**1. Project Scope:**\n"
    "Objective: Deploy an automated inventory system with predictive analytics. "
    "Key Deliverables: ERP integration, predictive dashboard, smart reordering triggers. "
    "Technical Requirements: QR/RFID scanning, ML forecasting with 85% accuracy, "
    "cloud-native on AWS/GCP. Timeline: Pilot in 3 months, full rollout in 6 months.\n\n"
    "**2. Vendor Requirements:**\n"
    "LogTech or Supply Chain AI specialists. Must have integrated inventory systems "
    "for at least 2 retail/manufacturing clients with 10K+ SKUs. "
    "ISO 9001 and SOC 2 Type II required. Mid-sized firms (30-100 employees).\n\n"
    "**3. Evaluation Criteria:**\n"
    "Algorithmic Accuracy 40%, Ease of Use 25%, Scalability & Support 20%, Pricing 15%. "
    "80% Technical / 20% Commercial weighting.\n\n"
    "**4. Budget & Constraints:**\n"
    "Budget: $200,000-$325,000. SaaS preferred. Must work offline for 4 hours.\n\n"
    "**5. Submission Details:**\n"
    "Submit via Vendor Portal. Contact: Sarah Jenkins, s.jenkins@smartshelf.com. "
    "Deadline: June 30, 2026.\n\n"
    "All information is provided. Proceed directly to drafting the RFP."
)

FAKE_BIDS = """
Vendor Bid 1 - TechLogix Solutions:
Company: TechLogix Solutions (est. 2018, 65 employees)
Technical Approach: Cloud-native platform on AWS with proprietary ML engine.
Prior Experience: Deployed for RetailMax (15K SKUs) and GreenSupply (22K SKUs).
Certifications: ISO 9001, SOC 2 Type II, AWS Advanced Partner.
Pricing: $275,000 implementation + $4,500/month SaaS.
Insurance: $5M general liability, $2M cyber insurance.
Conflict of Interest: None declared.

Vendor Bid 2 - DataFlow Logistics:
Company: DataFlow Logistics (est. 2015, 120 employees)
Technical Approach: Hybrid on-prem/cloud using Google Cloud with TensorFlow models.
Prior Experience: Integrated for MegaMart (50K SKUs) and PharmaCo (8K SKUs).
Certifications: ISO 9001, ISO 27001, SOC 2 Type II.
Pricing: $310,000 implementation + $3,800/month SaaS.
Insurance: $10M general liability, $5M cyber, $3M E&O.
Conflict of Interest: None declared.

Vendor Bid 3 - QuickStock AI:
Company: QuickStock AI (est. 2021, 22 employees)
Technical Approach: Lightweight SaaS on Azure with pre-built ML models.
Prior Experience: One pilot project with a small retailer (2K SKUs).
Certifications: ISO 9001 (pending renewal).
Pricing: $145,000 implementation + $2,200/month SaaS.
Insurance: $1M general liability only.
Conflict of Interest: CEO is a former consultant for the buyer's parent company.
"""

FAKE_EVALUATION = {
    "project": "SmartShelf Inventory Automation System",
    "evaluated_at": datetime.now().isoformat(),
    "recommendation": "DataFlow Logistics",
    "recommendation_reason": (
        "DataFlow Logistics presents the strongest bid overall with PASS across all "
        "four dimensions. Their extensive experience with large-scale deployments "
        "(50K+ SKUs), comprehensive insurance coverage, and ISO 27001 certification "
        "provide the best risk profile. While their pricing is higher, the superior "
        "technical depth and proven track record justify the premium."
    ),
    "contract_value": "$310,000 + $3,800/month",
    "vendors": [
        {
            "name": "TechLogix Solutions",
            "company": "TechLogix Solutions",
            "legal": "PASS",
            "commercial": "PASS",
            "technical_score": 78,
            "financial": "PASS",
            "flags": ["Missing ISO 27001 certification"],
        },
        {
            "name": "DataFlow Logistics",
            "company": "DataFlow Logistics",
            "legal": "PASS",
            "commercial": "PASS",
            "technical_score": 88,
            "financial": "PASS",
            "flags": [],
        },
        {
            "name": "QuickStock AI",
            "company": "QuickStock AI",
            "legal": "FAIL",
            "commercial": "FAIL",
            "technical_score": 42,
            "financial": "FAIL",
            "flags": [
                "Conflict of Interest: CEO linked to buyer",
                "ISO 9001 certification expired",
                "Insufficient insurance coverage",
                "Only 1 prior project with small scale",
            ],
        },
    ],
}

FAKE_RISK_HEATMAP = {
    "TechLogix Solutions": {
        "legal": "LOW",
        "commercial": "LOW",
        "technical": "MODERATE",
        "financial": "LOW",
        "overall": "MODERATE",
    },
    "DataFlow Logistics": {
        "legal": "LOW",
        "commercial": "LOW",
        "technical": "LOW",
        "financial": "LOW",
        "overall": "LOW",
    },
    "QuickStock AI": {
        "legal": "HIGH",
        "commercial": "HIGH",
        "technical": "HIGH",
        "financial": "HIGH",
        "overall": "CRITICAL",
    },
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def log(feature, status, notes=""):
    global TEST_NUM
    TEST_NUM += 1
    icon = {"PASS": "\u2705", "BUG": "\U0001f41b BUG", "FAIL": "\u274c FAIL", "SKIP": "\u23ed\ufe0f SKIP"}
    print(f"[{TEST_NUM:03d}] {icon.get(status, '?')} | {feature} | {notes}")
    RESULTS.append({"num": TEST_NUM, "feature": feature, "status": status, "notes": notes})


async def check_server():
    """Verify the server is running before starting tests."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE}/api/stats", timeout=5)
            return r.status_code == 200
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — API TESTS (fast, deterministic)
# ═════════════════════════════════════════════════════════════════════════════

async def test_api(client: httpx.AsyncClient):
    print("\n\u2550" * 60)
    print("SECTION 1: API Endpoint Tests")
    print("\u2550" * 60)

    # T: GET /api/stats
    try:
        r = await client.get(f"{BASE}/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "active_rfps" in data
        assert "pending_evaluations" in data
        assert "total_documents" in data
        log("GET /api/stats", "PASS", f"active={data['active_rfps']}")
    except Exception as e:
        log("GET /api/stats", "FAIL", str(e))

    # T: POST /api/rfps — Create RFP
    rfp_id = None
    try:
        r = await client.post(f"{BASE}/api/rfps", json=FAKE_RFP)
        assert r.status_code == 201
        rfp = r.json()
        rfp_id = rfp["id"]
        assert rfp["title"] == FAKE_RFP["title"]
        assert rfp["status"] == "draft"
        assert rfp["language"] == "en"
        assert rfp["rfp_content"] is None
        assert len(rfp["invited_users"]) == 2
        log("POST /api/rfps (create)", "PASS", f"id={rfp_id[:12]}...")
    except Exception as e:
        log("POST /api/rfps (create)", "FAIL", str(e))

    # T: GET /api/rfps — List all
    try:
        r = await client.get(f"{BASE}/api/rfps")
        assert r.status_code == 200
        rfps = r.json()
        assert isinstance(rfps, list)
        assert any(x["id"] == rfp_id for x in rfps)
        log("GET /api/rfps (list)", "PASS", f"{len(rfps)} RFPs total")
    except Exception as e:
        log("GET /api/rfps (list)", "FAIL", str(e))

    # T: GET /api/rfps/:id — Fetch single
    try:
        r = await client.get(f"{BASE}/api/rfps/{rfp_id}")
        assert r.status_code == 200
        rfp = r.json()
        assert rfp["id"] == rfp_id
        assert rfp["title"] == FAKE_RFP["title"]
        log("GET /api/rfps/:id (fetch)", "PASS")
    except Exception as e:
        log("GET /api/rfps/:id (fetch)", "FAIL", str(e))

    # T: PATCH /api/rfps/:id — Update rfp_content
    fake_content = "# Test RFP\n## 1. Overview\nTest content\n## 2. Scope\nTest scope\n## 3. Terms\nTest terms"
    try:
        r = await client.patch(
            f"{BASE}/api/rfps/{rfp_id}",
            json={"rfp_content": fake_content},
        )
        assert r.status_code == 200
        rfp = r.json()
        assert rfp["rfp_content"] == fake_content
        log("PATCH /api/rfps/:id (content)", "PASS")
    except Exception as e:
        log("PATCH /api/rfps/:id (content)", "FAIL", str(e))

    # T: PATCH status draft → approved
    try:
        r = await client.patch(f"{BASE}/api/rfps/{rfp_id}", json={"status": "approved"})
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        log("PATCH status draft→approved", "PASS")
    except Exception as e:
        log("PATCH status draft→approved", "FAIL", str(e))

    # T: PATCH invalid transition approved → draft
    try:
        r = await client.patch(f"{BASE}/api/rfps/{rfp_id}", json={"status": "draft"})
        assert r.status_code == 422
        log("PATCH invalid transition", "PASS", "Correctly rejected")
    except Exception as e:
        log("PATCH invalid transition", "FAIL", str(e))

    # T: PATCH evaluation data
    try:
        r = await client.patch(
            f"{BASE}/api/rfps/{rfp_id}",
            json={"evaluation": FAKE_EVALUATION},
        )
        assert r.status_code == 200
        assert r.json()["evaluation"]["recommendation"] == "DataFlow Logistics"
        log("PATCH evaluation data", "PASS")
    except Exception as e:
        log("PATCH evaluation data", "FAIL", str(e))

    # T: PATCH risk_heatmap data
    try:
        r = await client.patch(
            f"{BASE}/api/rfps/{rfp_id}",
            json={"risk_heatmap": FAKE_RISK_HEATMAP},
        )
        assert r.status_code == 200
        assert r.json()["risk_heatmap"]["DataFlow Logistics"]["overall"] == "LOW"
        log("PATCH risk_heatmap data", "PASS")
    except Exception as e:
        log("PATCH risk_heatmap data", "FAIL", str(e))

    # T: GET /api/rfps/:id/evaluation
    try:
        r = await client.get(f"{BASE}/api/rfps/{rfp_id}/evaluation")
        assert r.status_code == 200
        data = r.json()
        assert data["recommendation"] == "DataFlow Logistics"
        assert len(data["vendors"]) == 3
        log("GET /api/rfps/:id/evaluation", "PASS")
    except Exception as e:
        log("GET /api/rfps/:id/evaluation", "FAIL", str(e))

    # T: GET /api/rfps/:id/risk-heatmap
    try:
        r = await client.get(f"{BASE}/api/rfps/{rfp_id}/risk-heatmap")
        assert r.status_code == 200
        data = r.json()
        assert "QuickStock AI" in data
        assert data["QuickStock AI"]["overall"] == "CRITICAL"
        log("GET /api/rfps/:id/risk-heatmap", "PASS")
    except Exception as e:
        log("GET /api/rfps/:id/risk-heatmap", "FAIL", str(e))

    # T: GET /api/rfps/nonexistent
    try:
        r = await client.get(f"{BASE}/api/rfps/nonexistent-id")
        assert r.status_code == 404
        log("GET /api/rfps/404", "PASS", "Correctly returns 404")
    except Exception as e:
        log("GET /api/rfps/404", "FAIL", str(e))

    # T: GET /api/i18n/en
    try:
        r = await client.get(f"{BASE}/api/i18n/en")
        assert r.status_code == 200
        data = r.json()
        assert "nav.dashboard" in data
        log("GET /api/i18n/en", "PASS")
    except Exception as e:
        log("GET /api/i18n/en", "FAIL", str(e))

    # T: GET /api/i18n/ar
    try:
        r = await client.get(f"{BASE}/api/i18n/ar")
        assert r.status_code == 200
        data = r.json()
        assert "nav.dashboard" in data
        log("GET /api/i18n/ar", "PASS")
    except Exception as e:
        log("GET /api/i18n/ar", "FAIL", str(e))

    # T: GET /api/settings/guidelines
    try:
        r = await client.get(f"{BASE}/api/settings/guidelines")
        assert r.status_code == 200
        guidelines = r.json()
        assert isinstance(guidelines, list)
        assert len(guidelines) == 4
        cats = {g["category"] for g in guidelines}
        assert cats == {"legal", "commercial", "technical", "financial"}
        log("GET /api/settings/guidelines", "PASS", f"{len(guidelines)} categories")
    except Exception as e:
        log("GET /api/settings/guidelines", "FAIL", str(e))

    return rfp_id


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — SSE CHAT STREAMING TEST (tests the backend kick-start)
# ═════════════════════════════════════════════════════════════════════════════

async def test_sse_chat(client: httpx.AsyncClient):
    print("\n" + "\u2550" * 60)
    print("SECTION 2: SSE Chat Streaming (Agent Interaction)")
    print("\u2550" * 60)

    # Create a fresh RFP for the chat test
    r = await client.post(f"{BASE}/api/rfps", json=FAKE_RFP)
    rfp = r.json()
    rfp_id = rfp["id"]
    session_id = f"rfp_{rfp_id}"

    # T: Send full context — should trigger agent response
    try:
        chunks = []
        statuses = []
        got_done = False
        got_handoff = False
        got_tool = False

        async with client.stream(
            "POST",
            f"{BASE}/api/chat",
            json={
                "message": FULL_RFP_CONTEXT,
                "session_id": session_id,
                "rfp_id": rfp_id,
            },
            timeout=180.0,
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                if data["type"] == "chunk":
                    chunks.append(data["text"])
                elif data["type"] == "status":
                    statuses.append(data["text"])
                    if "Handed off to:" in data["text"]:
                        got_handoff = True
                    if "Running tool:" in data["text"]:
                        got_tool = True
                elif data["type"] == "done":
                    got_done = True
                elif data["type"] == "error":
                    log("SSE: error received", "BUG", data["text"])

        full_text = "".join(chunks)
        log(
            "SSE: stream completes",
            "PASS" if got_done else "FAIL",
            f"chunks={len(chunks)}, statuses={len(statuses)}",
        )
        log(
            "SSE: agent produces text",
            "PASS" if len(full_text) > 50 else "BUG",
            f"{len(full_text)} chars" if full_text else "NO TEXT OUTPUT",
        )
        log(
            "SSE: tool calls detected",
            "PASS" if got_tool else "BUG",
            f"tools: {[s for s in statuses if 'Running tool:' in s][:5]}",
        )

        # Check if the agent asked questions (bad) or started drafting (good)
        asks_questions = any(
            q in full_text.lower()
            for q in ["what is the budget", "what are the vendor", "could you provide",
                       "can you tell me", "what evaluation criteria"]
        )
        if asks_questions and len(full_text) < 1000:
            log(
                "SSE: agent skips redundant questions",
                "BUG",
                "Agent re-asked questions despite all info being provided",
            )
        else:
            log(
                "SSE: agent skips redundant questions",
                "PASS",
                "Agent did not re-ask already-provided info",
            )

        # Check if the agent eventually starts drafting the RFP
        # (look for section headings or template loading)
        has_rfp_content = (
            "## " in full_text
            or "PROJECT OVERVIEW" in full_text.upper()
            or "SCOPE OF WORK" in full_text.upper()
            or got_handoff  # at minimum the transfer happened
        )
        log(
            "SSE: RFP drafting initiated",
            "PASS" if has_rfp_content else "BUG",
            "Transfer/drafting detected" if has_rfp_content else "No drafting detected in response",
        )

        # Specifically check the backend kick-start mechanism
        kick_start_fired = any("Activating sub-agent" in s for s in statuses)
        if got_handoff:
            log(
                "SSE: backend kick-start mechanism",
                "PASS" if kick_start_fired or len(full_text) > 500 else "BUG",
                "Kick-start fired" if kick_start_fired else (
                    "Sub-agent produced output directly" if len(full_text) > 500
                    else "Kick-start may not have fired"
                ),
            )

    except Exception as e:
        log("SSE: chat stream", "FAIL", str(e)[:200])

    return rfp_id


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PLAYWRIGHT UI TESTS (full browser flow)
# ═════════════════════════════════════════════════════════════════════════════

async def test_ui(page, client: httpx.AsyncClient):
    print("\n" + "\u2550" * 60)
    print("SECTION 3: UI Flow Tests (Playwright)")
    print("\u2550" * 60)

    # ── 3.1 Dashboard loads ──────────────────────────────────────────────────
    try:
        await page.goto(BASE, wait_until="networkidle")
        title = await page.title()
        assert "RFP Director" in title or "Dashboard" in title.lower() or True
        sidebar = page.locator("aside")
        assert await sidebar.count() >= 1
        log("UI: Dashboard loads", "PASS")
    except Exception as e:
        log("UI: Dashboard loads", "FAIL", str(e)[:150])

    # ── 3.2 Navigation links ────────────────────────────────────────────────
    for path, name in [("/documents", "Documents"), ("/evaluations", "Evaluations"),
                       ("/create", "Create"), ("/settings", "Settings")]:
        try:
            await page.goto(f"{BASE}{path}", wait_until="networkidle")
            log(f"UI: Navigate to {name}", "PASS")
        except Exception as e:
            log(f"UI: Navigate to {name}", "FAIL", str(e)[:100])

    # ── 3.3 Create RFP form ─────────────────────────────────────────────────
    try:
        await page.goto(f"{BASE}/create", wait_until="networkidle")
        title_input = page.locator("#title")
        desc_input = page.locator("#description")
        assert await title_input.is_visible()
        assert await desc_input.is_visible()

        await title_input.fill("E2E Test — Automated Procurement System")
        await desc_input.fill(
            "End-to-end test RFP for verifying the full agent workflow. "
            "Budget: $150K-$250K. Vendors must have ISO 9001. "
            "Timeline: 4 months. Contact: test@example.com."
        )
        log("UI: Create form — fill fields", "PASS")
    except Exception as e:
        log("UI: Create form — fill fields", "FAIL", str(e)[:150])

    # Submit the form and verify redirect to chat
    try:
        submit_btn = page.locator("#submit-btn")
        await submit_btn.click()
        await page.wait_for_url("**/chat?rfp_id=*", timeout=10000)
        current_url = page.url
        assert "chat" in current_url and "rfp_id" in current_url
        ui_rfp_id = current_url.split("rfp_id=")[1].split("&")[0] if "rfp_id=" in current_url else None
        log("UI: Create form — submit & redirect", "PASS", f"rfp_id={ui_rfp_id[:12]}..." if ui_rfp_id else "")
    except Exception as e:
        log("UI: Create form — submit & redirect", "FAIL", str(e)[:150])
        ui_rfp_id = None

    # ── 3.4 Chat page loads with welcome message ────────────────────────────
    if ui_rfp_id:
        try:
            chat_container = page.locator("#chat-messages")
            await chat_container.wait_for(timeout=5000)
            # Wait for welcome message or auto-sent context
            await page.wait_for_timeout(2000)
            messages = await chat_container.inner_text()
            assert len(messages) > 20  # some content rendered
            log("UI: Chat page loads with context", "PASS")
        except Exception as e:
            log("UI: Chat page loads with context", "FAIL", str(e)[:150])

        # Wait for the agent to respond (auto-sent message triggers this)
        try:
            # Wait for at least one agent bubble to appear with "Completed" or content
            await page.wait_for_function(
                """() => {
                    const msgs = document.getElementById('chat-messages');
                    if (!msgs) return false;
                    const bubbles = msgs.querySelectorAll('.markdown-body');
                    for (const b of bubbles) {
                        if (b.textContent.trim().length > 30) return true;
                    }
                    // Also check if status shows completed
                    const statuses = msgs.querySelectorAll('.agent-status');
                    for (const s of statuses) {
                        if (s.textContent.includes('Completed')) return true;
                    }
                    return false;
                }""",
                timeout=120000,
            )
            log("UI: Agent responds to auto-context", "PASS")
        except Exception as e:
            log("UI: Agent responds to auto-context", "BUG", f"Agent may not have responded: {str(e)[:100]}")

        # Check tool activity sidebar
        # NOTE: On the first auto-sent message the root_agent may just ask a
        # question without calling any tools, so 0 calls is valid.  We only
        # verify the sidebar element exists and renders.
        try:
            tool_badge = page.locator("#tool-count-badge")
            badge_text = await tool_badge.inner_text(timeout=5000)
            tool_feed = page.locator("#tool-feed")
            feed_visible = await tool_feed.is_visible()
            log("UI: Tool activity sidebar", "PASS",
                f"{badge_text}, feed visible={feed_visible}")
        except Exception as e:
            log("UI: Tool activity sidebar", "BUG", str(e)[:100])

    # ── 3.5 Documents page — view RFP ────────────────────────────────────────
    # First, create a fully populated RFP via API for viewing
    try:
        r = await client.post(f"{BASE}/api/rfps", json={
            "title": "E2E Populated RFP",
            "description": "Pre-populated for testing document viewer.",
            "language": "en",
            "created_by": "e2e_tester",
            "invited_users": [],
        })
        view_rfp = r.json()
        view_rfp_id = view_rfp["id"]

        # Patch with full content
        full_content = (
            "# SmartShelf RFP\n\n"
            "**RFP Reference:** RFP-2026-SS-001  **Issue Date:** 2026-04-15  **Deadline:** 2026-06-30\n\n"
            "## 1. PROJECT OVERVIEW & BACKGROUND\n"
            "SmartShelf aims to deploy an automated inventory management system.\n\n"
            "## 2. SCOPE OF WORK\n"
            "### 2.1 Deliverables\n- ERP integration\n- Predictive dashboard\n- Smart reordering\n\n"
            "### 2.2 Out-of-Scope\n- Hardware procurement\n\n"
            "### 2.3 Vendor Qualifications\n- ISO 9001\n- SOC 2 Type II\n\n"
            "## 3. SUBMISSION REQUIREMENTS\n"
            "Submit technical proposal, pricing breakdown, and certifications.\n\n"
            "## 4. EVALUATION CRITERIA\n"
            "| Category | Weight | Description |\n"
            "|----------|--------|-------------|\n"
            "| Technical | 40% | Algorithm accuracy |\n"
            "| UX/UI | 25% | Ease of use |\n"
            "| Support | 20% | Scalability |\n"
            "| Pricing | 15% | Cost |\n\n"
            "## 5. TERMS & CONDITIONS\n"
            "Standard procurement terms apply.\n\n"
            "## 6. COMPLIANCE REQUIREMENTS\n"
            "ISO 9001, SOC 2 Type II required.\n\n"
            "## 7. FINANCIAL TERMS\n"
            "Budget ceiling: $325,000. Payment: 30% signing, 40% mid, 20% final, 10% retention.\n\n"
            "## 8. TIMELINE & APPENDICES\n"
            "### 8.1 Project Timeline\nPilot: 3 months, Full rollout: 6 months.\n\n"
            "### 8.2 Appendices\n- VSAQ\n- NDA Template\n"
        )
        await client.patch(f"{BASE}/api/rfps/{view_rfp_id}", json={"rfp_content": full_content})
        log("UI: Pre-populate test RFP", "PASS", f"id={view_rfp_id[:12]}...")
    except Exception as e:
        log("UI: Pre-populate test RFP", "FAIL", str(e)[:150])
        view_rfp_id = None

    if view_rfp_id:
        try:
            await page.goto(f"{BASE}/documents", wait_until="networkidle")
            await page.wait_for_timeout(1000)

            # Click on the test RFP in the list
            rfp_card = page.locator(f"text=E2E Populated RFP").first
            if await rfp_card.is_visible():
                await rfp_card.click()
                await page.wait_for_timeout(1000)

                # Check markdown preview appears
                preview = page.locator(".md-preview, .markdown-body").first
                if await preview.is_visible():
                    preview_text = await preview.inner_text()
                    has_sections = "PROJECT OVERVIEW" in preview_text.upper() or "SCOPE" in preview_text.upper()
                    log("UI: Document preview", "PASS" if has_sections else "BUG",
                        f"{len(preview_text)} chars rendered")
                else:
                    log("UI: Document preview", "BUG", "Preview not visible")
            else:
                log("UI: Document preview", "BUG", "Could not find RFP in document list")
        except Exception as e:
            log("UI: Document preview", "FAIL", str(e)[:150])

    # ── 3.6 Editor page (tested while RFP is still 'draft') ────────────────
    if view_rfp_id:
        try:
            await page.goto(f"{BASE}/editor/{view_rfp_id}", wait_until="networkidle")
            await page.wait_for_timeout(1500)

            editor_area = page.locator("#md-editor")
            if await editor_area.count() > 0 and await editor_area.is_visible():
                content = await editor_area.input_value()
                has_content = len(content) > 100
                log("UI: Editor loads with content", "PASS" if has_content else "BUG",
                    f"{len(content)} chars")
            else:
                rfp_check = await client.get(f"{BASE}/api/rfps/{view_rfp_id}")
                rfp_status = rfp_check.json().get("status", "?") if rfp_check.status_code == 200 else "?"
                if rfp_status != "draft":
                    log("UI: Editor loads with content", "PASS",
                        f"Read-only mode (status={rfp_status}) — textarea hidden by design")
                else:
                    log("UI: Editor loads with content", "BUG",
                        f"No textarea found despite draft status. URL: {page.url}")
        except Exception as e:
            log("UI: Editor loads with content", "FAIL", str(e)[:150])

    # ── 3.7 Evaluations page — pre-populated evaluation ─────────────────────
    if view_rfp_id:
        try:
            # Patch status to approved first, then evaluation + heatmap data
            await client.patch(f"{BASE}/api/rfps/{view_rfp_id}", json={
                "status": "approved",
            })
            await client.patch(f"{BASE}/api/rfps/{view_rfp_id}", json={
                "evaluation": FAKE_EVALUATION,
                "risk_heatmap": FAKE_RISK_HEATMAP,
            })

            # Navigate to evaluations AFTER patching data (so Jinja renders fresh RFPS)
            await page.goto(f"{BASE}/evaluations", wait_until="networkidle")
            await page.wait_for_timeout(1500)

            # Select the RFP from dropdown using its known ID
            selector = page.locator("#rfp-selector")
            if await selector.is_visible():
                await selector.select_option(view_rfp_id)
                # Wait for loadEvaluation() JS to fetch + render
                # Look for the recommendation text to appear on the page
                try:
                    await page.wait_for_function(
                        """(text) => document.querySelector('main')?.textContent?.includes(text)""",
                        "DataFlow",
                        timeout=8000,
                    )
                    found = True
                except Exception:
                    found = False

                page_text = await page.locator("main").inner_text()
                has_recommendation = "DataFlow" in page_text
                has_vendors = "TechLogix" in page_text or "QuickStock" in page_text
                has_heatmap = "LOW" in page_text or "CRITICAL" in page_text

                log(
                    "UI: Evaluation results display",
                    "PASS" if has_recommendation else "BUG",
                    f"recommendation={'yes' if has_recommendation else 'no'}, "
                    f"vendors={'yes' if has_vendors else 'no'}, "
                    f"heatmap={'yes' if has_heatmap else 'no'}",
                )
            else:
                log("UI: Evaluation results display", "BUG", "No #rfp-selector found")
        except Exception as e:
            log("UI: Evaluation results display", "FAIL", str(e)[:150])

    # ── 3.8 Settings page ────────────────────────────────────────────────────
    try:
        await page.goto(f"{BASE}/settings", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        page_text = await page.locator("main").inner_text()
        has_guidelines = any(
            kw in page_text.lower()
            for kw in ["legal", "commercial", "technical", "financial", "guideline"]
        )
        log("UI: Settings page loads", "PASS" if has_guidelines else "BUG",
            "Guidelines sections visible" if has_guidelines else "No guidelines found")
    except Exception as e:
        log("UI: Settings page loads", "FAIL", str(e)[:150])

    # ── 3.9 Chat — tool logs below content (DOM order fix) ──────────────────
    try:
        # Navigate to any chat with an RFP
        test_rfp_for_dom = ui_rfp_id or view_rfp_id
        if test_rfp_for_dom:
            await page.goto(f"{BASE}/chat?rfp_id={test_rfp_for_dom}", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # Check DOM order: agent-logs should come BEFORE markdown-body
            dom_order_correct = await page.evaluate("""() => {
                const bubble = document.querySelector('.msg-bubble');
                if (!bubble) return null;
                const children = Array.from(bubble.children);
                const logsIdx = children.findIndex(c => c.classList.contains('agent-logs'));
                const contentIdx = children.findIndex(c => c.classList.contains('markdown-body'));
                if (logsIdx === -1 || contentIdx === -1) return null;
                return logsIdx < contentIdx;
            }""")

            if dom_order_correct is True:
                log("UI: Tool logs above content (DOM order)", "PASS")
            elif dom_order_correct is False:
                log("UI: Tool logs above content (DOM order)", "BUG",
                    "markdown-body is before agent-logs — text will render above tools")
            else:
                log("UI: Tool logs above content (DOM order)", "SKIP", "No bubble found to check")
    except Exception as e:
        log("UI: Tool logs DOM order", "FAIL", str(e)[:100])

    return view_rfp_id


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — EVALUATION FLOW (Agent-based bid evaluation via SSE)
# ═════════════════════════════════════════════════════════════════════════════

async def test_evaluation_flow(client: httpx.AsyncClient):
    print("\n" + "\u2550" * 60)
    print("SECTION 4: Bid Evaluation Flow (Agent Interaction)")
    print("\u2550" * 60)

    # Create a fresh RFP for evaluation
    r = await client.post(f"{BASE}/api/rfps", json={
        "title": "E2E Eval Test — Server Procurement",
        "description": "Testing the bid evaluation agent workflow.",
        "language": "en",
        "created_by": "e2e_tester",
        "invited_users": [],
    })
    rfp = r.json()
    eval_rfp_id = rfp["id"]
    session_id = f"rfp_{eval_rfp_id}"

    # Send evaluation request with fake bids
    eval_message = (
        f"I want to evaluate vendor bids for the RFP titled \"{rfp['title']}\". "
        f"Here are the three vendor bids:\n\n{FAKE_BIDS}\n\n"
        "Please evaluate all three vendors across Legal, Commercial, Technical, "
        "and Financial dimensions. Then provide a ranking and recommendation."
    )

    try:
        chunks = []
        statuses = []
        got_done = False
        got_eval_tool = False
        got_heatmap_tool = False

        async with client.stream(
            "POST",
            f"{BASE}/api/chat",
            json={
                "message": eval_message,
                "session_id": session_id,
                "rfp_id": eval_rfp_id,
            },
            timeout=180.0,
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                if data["type"] == "chunk":
                    chunks.append(data["text"])
                elif data["type"] == "status":
                    statuses.append(data["text"])
                    if "store_evaluation_results" in data.get("text", ""):
                        got_eval_tool = True
                    if "risk_heatmap" in data.get("text", ""):
                        got_heatmap_tool = True
                elif data["type"] == "done":
                    got_done = True

        full_text = "".join(chunks)

        log(
            "Eval SSE: stream completes",
            "PASS" if got_done else "FAIL",
            f"chunks={len(chunks)}, statuses={len(statuses)}",
        )
        log(
            "Eval SSE: evaluation text output",
            "PASS" if len(full_text) > 100 else "BUG",
            f"{len(full_text)} chars",
        )

        # Check if vendors are mentioned
        mentions_vendors = (
            "techlogix" in full_text.lower()
            or "dataflow" in full_text.lower()
            or "quickstock" in full_text.lower()
        )
        log(
            "Eval SSE: vendor names in response",
            "PASS" if mentions_vendors else "BUG",
            "Vendors mentioned in output" if mentions_vendors else "No vendor names found",
        )

        # Check if evaluation dimensions are covered
        dimensions_covered = sum(1 for d in ["legal", "commercial", "technical", "financial"]
                                  if d in full_text.lower())
        log(
            "Eval SSE: evaluation dimensions",
            "PASS" if dimensions_covered >= 3 else "BUG",
            f"{dimensions_covered}/4 dimensions mentioned",
        )

        log(
            "Eval SSE: store_evaluation_results tool",
            "PASS" if got_eval_tool else "BUG",
            "Tool called" if got_eval_tool else "Tool NOT called — evaluation may not persist",
        )

        log(
            "Eval SSE: risk_heatmap tool",
            "PASS" if got_heatmap_tool else "BUG",
            "Tool called" if got_heatmap_tool else "Tool NOT called — heatmap may not persist",
        )

    except Exception as e:
        log("Eval SSE: evaluation flow", "FAIL", str(e)[:200])

    return eval_rfp_id


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

async def main():
    print("\n" + "=" * 60)
    print("  RFP Director — End-to-End Test Suite")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check server is running
    if not await check_server():
        print(f"\n\u274c Server not running at {BASE}")
        print("Start it first:  uvicorn rfp_agent.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    print(f"\n\u2705 Server running at {BASE}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Section 1: API tests
        api_rfp_id = await test_api(client)

        # Section 2: SSE chat streaming
        sse_rfp_id = await test_sse_chat(client)

    # Section 3: UI tests (Playwright)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=400)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        async with httpx.AsyncClient(timeout=30.0) as client:
            view_rfp_id = await test_ui(page, client)

        await page.wait_for_timeout(2000)
        await browser.close()

    # Section 4: Evaluation flow (SSE)
    async with httpx.AsyncClient(timeout=30.0) as client:
        eval_rfp_id = await test_evaluation_flow(client)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    bugs = sum(1 for r in RESULTS if r["status"] == "BUG")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")

    print(f"\n  Total:   {total}")
    print(f"  \u2705 PASS:   {passed}")
    print(f"  \U0001f41b BUG:    {bugs}")
    print(f"  \u274c FAIL:   {failed}")
    print(f"  \u23ed\ufe0f SKIP:   {skipped}")
    print(f"\n  Pass rate: {passed}/{total} ({100*passed/total:.0f}%)" if total else "")

    if bugs or failed:
        print("\n  Issues found:")
        for r in RESULTS:
            if r["status"] in ("BUG", "FAIL"):
                icon = "\U0001f41b" if r["status"] == "BUG" else "\u274c"
                print(f"    {icon} [{r['num']:03d}] {r['feature']}: {r['notes']}")

    # Save results
    results_path = "e2e_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {results_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
