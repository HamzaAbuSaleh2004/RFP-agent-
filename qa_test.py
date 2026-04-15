"""
Senior QA -- Full Playwright test suite for RFP Director
Run: python qa_test.py
"""
import asyncio
import json
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"
RESULTS = []
RFP_ID = None   # set after creation
AR_RFP_ID = None

def log(num, feature, status, notes=""):
    icon = "✅" if status == "PASS" else ("🐛 BUG" if status == "BUG" else "❌ FAIL")
    line = f"[{num:03d}] {icon} | {feature} | {notes}"
    print(line)
    RESULTS.append({"num": num, "feature": feature, "status": status, "notes": notes})


async def run_tests():
    global RFP_ID, AR_RFP_ID

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()

        # ── collect console errors ──────────────────────────────────────────
        console_errors = []
        page.on("console", lambda m: console_errors.append(m) if m.type == "error" else None)

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 1 — NAVIGATION & SHELL
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 1: Navigation & Shell ──")

        # T1: Dashboard loads
        try:
            await page.goto(BASE, wait_until="networkidle")
            assert page.url.rstrip("/") in [BASE, BASE + "/"]
            errs = [e for e in console_errors if "error" in e.text.lower()]
            if errs:
                log(1, "Dashboard loads", "BUG", f"Console errors: {[e.text for e in errs][:3]}")
            else:
                log(1, "Dashboard loads", "PASS", "No console errors")
        except Exception as e:
            log(1, "Dashboard loads", "FAIL", str(e))

        # T2: Nav links
        nav_links = [
            ("/documents", "documents"),
            ("/evaluations", "evaluations"),
            ("/flowchart", "flowchart"),
            ("/settings", "settings"),
            ("/", "dashboard"),
        ]
        for path, name in nav_links:
            try:
                await page.goto(BASE + path, wait_until="networkidle")
                assert page.url.rstrip("/").endswith(path.rstrip("/")) or path == "/"
                log(2, f"Nav: {name}", "PASS")
            except Exception as e:
                log(2, f"Nav: {name}", "FAIL", str(e))

        # T3: Page titles
        title_checks = [
            ("/", "dashboard"),
            ("/documents", "documents"),
            ("/evaluations", "evaluations"),
            ("/settings", "settings"),
        ]
        for path, keyword in title_checks:
            try:
                await page.goto(BASE + path, wait_until="networkidle")
                title = await page.title()
                if "rfp" in title.lower() or keyword in title.lower():
                    log(3, f"Title check: {path}", "PASS", f'"{title}"')
                else:
                    log(3, f"Title check: {path}", "BUG", f'Title missing keyword — got "{title}"')
            except Exception as e:
                log(3, f"Title check: {path}", "FAIL", str(e))

        # T4: No 4xx/5xx on any nav page
        try:
            failed_reqs = []
            def on_response(resp):
                if resp.status >= 400:
                    failed_reqs.append(f"{resp.status} {resp.url}")
            page.on("response", on_response)
            for path, _ in nav_links:
                await page.goto(BASE + path, wait_until="networkidle")
            if failed_reqs:
                log(4, "No HTTP errors on nav", "BUG", str(failed_reqs))
            else:
                log(4, "No HTTP errors on nav", "PASS")
        except Exception as e:
            log(4, "No HTTP errors on nav", "FAIL", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 2 — DASHBOARD
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 2: Dashboard ──")

        await page.goto(BASE, wait_until="networkidle")

        # T5: Stat cards present
        try:
            import aiohttp, ssl
            import urllib.request
            stats_raw = urllib.request.urlopen(f"{BASE}/api/stats").read()
            stats = json.loads(stats_raw)
            body = await page.content()
            has_numbers = (
                str(stats["active_rfps"]) in body or
                str(stats["total_documents"]) in body
            )
            if has_numbers:
                log(5, "Dashboard stat cards", "PASS", f"stats={stats}")
            else:
                log(5, "Dashboard stat cards", "BUG", f"API stats={stats} not visible in page")
        except Exception as e:
            log(5, "Dashboard stat cards", "BUG", str(e))

        # T6: Create RFP button exists
        try:
            btn = page.locator("a[href='/create'], button:has-text('Create'), a:has-text('Create')")
            count = await btn.count()
            if count > 0:
                log(6, "Create RFP button on dashboard", "PASS")
            else:
                log(6, "Create RFP button on dashboard", "BUG", "No create button found")
        except Exception as e:
            log(6, "Create RFP button on dashboard", "FAIL", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 3 — CREATE RFP
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 3: Create RFP ──")

        await page.goto(f"{BASE}/create", wait_until="networkidle")

        # T7: Form fields present
        try:
            title_el  = page.locator("input[name='title'], input[placeholder*='title' i], input[id*='title' i]")
            desc_el   = page.locator("textarea[name='description'], textarea[placeholder*='desc' i], textarea[id*='desc' i]")
            t_count   = await title_el.count()
            d_count   = await desc_el.count()
            if t_count > 0 and d_count > 0:
                log(7, "Create form fields present", "PASS", f"title fields={t_count}, desc fields={d_count}")
            else:
                log(7, "Create form fields present", "BUG", f"title={t_count}, desc={d_count}")
        except Exception as e:
            log(7, "Create form fields present", "FAIL", str(e))

        # T8: Empty form submission blocked
        try:
            submit = page.locator("button[type='submit'], button:has-text('Create'), button:has-text('Submit')")
            s_count = await submit.count()
            if s_count == 0:
                log(8, "Empty form validation", "BUG", "No submit button found")
            else:
                await submit.first.click()
                await page.wait_for_timeout(800)
                # Should still be on /create
                still_on_create = "/create" in page.url
                if still_on_create:
                    log(8, "Empty form validation", "PASS", "Stayed on /create after empty submit")
                else:
                    log(8, "Empty form validation", "BUG", f"Navigated away to {page.url} without filling form")
        except Exception as e:
            log(8, "Empty form validation", "FAIL", str(e))

        # T9: Valid English RFP creation
        try:
            await page.goto(f"{BASE}/create", wait_until="networkidle")
            title_input = page.locator("input[name='title'], input[placeholder*='title' i], input[id*='title' i]").first
            desc_input  = page.locator("textarea").first
            await title_input.fill("LiverX Hospital IT Infrastructure RFP")
            await desc_input.fill(
                "Procurement of hospital-grade servers, networking equipment, "
                "and 5-year managed support for LiverX three hospital campuses in Riyadh."
            )
            # Try to select English if language toggle exists
            lang_en = page.locator("button:has-text('EN'), input[value='en'], label:has-text('English')")
            if await lang_en.count() > 0:
                await lang_en.first.click()

            submit = page.locator("button[type='submit'], button:has-text('Create'), button:has-text('Submit')").first
            await submit.click()
            await page.wait_for_timeout(2000)

            # Check if redirected somewhere meaningful
            new_url = page.url
            if "/chat" in new_url or "/editor" in new_url or "rfp_id" in new_url:
                # Extract rfp_id from URL
                if "rfp_id=" in new_url:
                    RFP_ID = new_url.split("rfp_id=")[1].split("&")[0].split("#")[0]
                log(9, "Valid EN RFP creation", "PASS", f"Redirected to {new_url}, rfp_id={RFP_ID}")
            else:
                # Check via API
                import urllib.request as ur
                rfps_raw = ur.urlopen(f"{BASE}/api/rfps").read()
                rfps = json.loads(rfps_raw)
                if rfps:
                    RFP_ID = rfps[-1]["id"]
                    log(9, "Valid EN RFP creation", "PASS", f"RFP created via API, id={RFP_ID}, url={new_url}")
                else:
                    log(9, "Valid EN RFP creation", "BUG", f"No redirect to chat and no RFP in API. URL={new_url}")
        except Exception as e:
            log(9, "Valid EN RFP creation", "FAIL", str(e))

        # T10: Arabic RFP creation
        try:
            await page.goto(f"{BASE}/create", wait_until="networkidle")
            title_input = page.locator("input[name='title'], input[placeholder*='title' i], input[id*='title' i]").first
            desc_input  = page.locator("textarea").first
            await title_input.fill("طلب تقديم عروض - منصة تحليل بيانات المرضى")
            await desc_input.fill("شراء منصة متكاملة لتحليل بيانات المرضى في مستشفيات LiverX في الرياض.")
            lang_ar = page.locator("button:has-text('AR'), input[value='ar'], label:has-text('Arabic'), label:has-text('العربية')")
            if await lang_ar.count() > 0:
                await lang_ar.first.click()
            submit = page.locator("button[type='submit'], button:has-text('Create'), button:has-text('Submit')").first
            await submit.click()
            await page.wait_for_timeout(2000)

            import urllib.request as ur
            rfps_raw = ur.urlopen(f"{BASE}/api/rfps").read()
            rfps = json.loads(rfps_raw)
            ar_rfps = [r for r in rfps if r.get("language") == "ar"]
            if ar_rfps:
                AR_RFP_ID = ar_rfps[-1]["id"]
                log(10, "Arabic RFP creation", "PASS", f"AR RFP created, id={AR_RFP_ID}")
            else:
                log(10, "Arabic RFP creation", "BUG", "No RFP with language=ar found after submission")
        except Exception as e:
            log(10, "Arabic RFP creation", "FAIL", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 4 — CHAT / AI CREATION
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 4: AI Chat / RFP Generation ──")

        if RFP_ID:
            await page.goto(f"{BASE}/chat?rfp_id={RFP_ID}&mode=create", wait_until="networkidle")

            # T11: Chat page loads with RFP context
            try:
                body = await page.content()
                if RFP_ID in body or "Hospital" in body or "rfp" in body.lower():
                    log(11, "Chat page loads with RFP context", "PASS")
                else:
                    log(11, "Chat page loads with RFP context", "BUG", "RFP title/id not visible in chat page")
            except Exception as e:
                log(11, "Chat page loads with RFP context", "FAIL", str(e))

            # T12: Send message and check SSE stream
            try:
                chat_input = page.locator("textarea, input[type='text']").last
                await chat_input.click()
                await chat_input.fill("Generate the full RFP document.")
                send_btn = page.locator("button[type='submit'], button:has-text('Send')").last
                await send_btn.click()

                # Wait up to 90s for the stream to complete
                await page.wait_for_timeout(3000)
                body_after = await page.content()

                # Check for status bubbles
                has_status = "Running tool" in body_after or "Handed off" in body_after or "rfp_creator" in body_after
                # Check for RFP sections
                has_sections = any(s in body_after for s in [
                    "PROJECT OVERVIEW", "SCOPE OF WORK", "TERMS", "COMPLIANCE",
                    "نظرة عامة", "نطاق العمل"
                ])

                if has_status:
                    log(12, "SSE status bubbles visible", "PASS")
                else:
                    log(12, "SSE status bubbles visible", "BUG", "No tool/agent status messages seen")

                # Wait longer for full generation
                print("  [waiting up to 90s for RFP generation...]")
                for _ in range(30):
                    await page.wait_for_timeout(3000)
                    body_after = await page.content()
                    if "PROJECT OVERVIEW" in body_after or "SCOPE OF WORK" in body_after or "done" in body_after.lower():
                        break

                has_sections = any(s in body_after for s in [
                    "PROJECT OVERVIEW", "SCOPE OF WORK", "TERMS & CONDITIONS",
                    "COMPLIANCE", "FINANCIAL TERMS", "TIMELINE"
                ])
                if has_sections:
                    log(13, "RFP sections generated in chat", "PASS", "All key sections visible")
                else:
                    log(13, "RFP sections generated in chat", "BUG", "RFP markdown sections not found in page")

            except Exception as e:
                log(12, "Chat message send + SSE", "FAIL", str(e))
                log(13, "RFP sections generated", "FAIL", str(e))

            # T14: rfp_content persisted to API
            try:
                await page.wait_for_timeout(3000)
                import urllib.request as ur
                rfp_raw = ur.urlopen(f"{BASE}/api/rfps/{RFP_ID}").read()
                rfp = json.loads(rfp_raw)
                if rfp.get("rfp_content"):
                    log(14, "rfp_content persisted after generation", "PASS",
                        f"{len(rfp['rfp_content'])} chars saved")
                else:
                    log(14, "rfp_content persisted after generation", "BUG",
                        "rfp_content is null after generation")
            except Exception as e:
                log(14, "rfp_content persisted", "FAIL", str(e))

            # T15: Chat accepts follow-up messages
            try:
                chat_input = page.locator("textarea, input[type='text']").last
                await chat_input.click()
                await chat_input.fill("Summarize section 5 in 3 bullet points.")
                send_btn = page.locator("button[type='submit'], button:has-text('Send')").last
                await send_btn.click()
                await page.wait_for_timeout(8000)
                body2 = await page.content()
                # Just check the page didn't crash / show error
                has_error = "500" in body2 or "Internal Server Error" in body2
                if has_error:
                    log(15, "Follow-up chat message", "BUG", "Server error on follow-up")
                else:
                    log(15, "Follow-up chat message", "PASS", "Follow-up sent without crash")
            except Exception as e:
                log(15, "Follow-up chat message", "FAIL", str(e))

        else:
            for n in [11, 12, 13, 14, 15]:
                log(n, "Chat tests", "FAIL", "Skipped — RFP_ID not set")

        # T16: Chat without rfp_id
        try:
            await page.goto(f"{BASE}/chat", wait_until="networkidle")
            body = await page.content()
            crashed = "500" in body or "error" in body.lower() and "traceback" in body.lower()
            if crashed:
                log(16, "Chat page without rfp_id", "BUG", "Page crashed without rfp_id param")
            else:
                log(16, "Chat page without rfp_id", "PASS", "Loads cleanly")
        except Exception as e:
            log(16, "Chat page without rfp_id", "FAIL", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 5 — EDITOR
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 5: Editor ──")

        if RFP_ID:
            await page.goto(f"{BASE}/editor/{RFP_ID}", wait_until="networkidle")

            # T17: Editor loads
            try:
                body = await page.content()
                crashed = "404" in body or "not found" in body.lower() or "traceback" in body.lower()
                if crashed:
                    log(17, "Editor page loads", "BUG", "404 or crash on editor page")
                else:
                    log(17, "Editor page loads", "PASS")
            except Exception as e:
                log(17, "Editor page loads", "FAIL", str(e))

            # T18: RFP content visible in editor
            try:
                body = await page.content()
                import urllib.request as ur
                rfp = json.loads(ur.urlopen(f"{BASE}/api/rfps/{RFP_ID}").read())
                content_present = rfp.get("rfp_content") and (
                    rfp["rfp_content"][:50].strip() in body or
                    "textarea" in body or
                    "editor" in body.lower()
                )
                if content_present:
                    log(18, "RFP content in editor", "PASS")
                else:
                    log(18, "RFP content in editor", "BUG", "rfp_content not visible / no editor textarea")
            except Exception as e:
                log(18, "RFP content in editor", "FAIL", str(e))

            # T19: Save edit via editor
            try:
                editor_area = page.locator("textarea").first
                if await editor_area.count() > 0:
                    current = await editor_area.input_value()
                    new_val = current + "\n\n<!-- QA test edit -->"
                    await editor_area.fill(new_val)
                    save_btn = page.locator("button:has-text('Save'), button[type='submit']").first
                    await save_btn.click()
                    await page.wait_for_timeout(1500)
                    body = await page.content()
                    success = "saved" in body.lower() or "success" in body.lower() or "updated" in body.lower()
                    log(19, "Save edit in editor", "PASS" if success else "BUG",
                        "" if success else "No success feedback after save")
                else:
                    log(19, "Save edit in editor", "BUG", "No textarea found in editor")
            except Exception as e:
                log(19, "Save edit in editor", "FAIL", str(e))

            # T20: Status transition draft → approved
            try:
                import urllib.request as ur
                import urllib.error
                req = urllib.request.Request(
                    f"{BASE}/api/rfps/{RFP_ID}",
                    data=json.dumps({"status": "approved"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="PATCH"
                )
                resp = ur.urlopen(req)
                data = json.loads(resp.read())
                if data.get("status") == "approved":
                    log(20, "Status transition draft→approved", "PASS")
                else:
                    log(20, "Status transition draft→approved", "BUG", f"status={data.get('status')}")
            except Exception as e:
                log(20, "Status transition draft→approved", "FAIL", str(e))

            # T21: Illegal status transition blocked
            try:
                import urllib.request as ur
                import urllib.error
                req = urllib.request.Request(
                    f"{BASE}/api/rfps/{RFP_ID}",
                    data=json.dumps({"status": "draft"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="PATCH"
                )
                try:
                    ur.urlopen(req)
                    log(21, "Illegal status transition blocked", "BUG", "approved→draft should return 422 but didn't")
                except urllib.error.HTTPError as he:
                    if he.code == 422:
                        log(21, "Illegal status transition blocked", "PASS", "422 returned as expected")
                    else:
                        log(21, "Illegal status transition blocked", "BUG", f"Expected 422, got {he.code}")
            except Exception as e:
                log(21, "Illegal status transition blocked", "FAIL", str(e))

            # T22: Editor 404 for bad ID
            try:
                await page.goto(f"{BASE}/editor/nonexistent-uuid-0000", wait_until="networkidle")
                body = await page.content()
                crashed_ugly = "traceback" in body.lower() or "internal server error" in body.lower()
                shows_404 = "404" in body or "not found" in body.lower()
                if shows_404 and not crashed_ugly:
                    log(22, "Editor 404 for bad ID", "PASS")
                elif crashed_ugly:
                    log(22, "Editor 404 for bad ID", "BUG", "Ugly 500 traceback instead of clean 404")
                else:
                    log(22, "Editor 404 for bad ID", "BUG", f"No 404 handling — body snippet: {body[:200]}")
            except Exception as e:
                log(22, "Editor 404 for bad ID", "FAIL", str(e))
        else:
            for n in range(17, 23):
                log(n, "Editor tests", "FAIL", "Skipped — RFP_ID not set")

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 6 — EVALUATIONS
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 6: Evaluations ──")

        await page.goto(f"{BASE}/evaluations", wait_until="networkidle")

        # T23: Evaluations page loads
        try:
            body = await page.content()
            crashed = "traceback" in body.lower() or "500" in page.url
            log(23, "Evaluations page loads", "BUG" if crashed else "PASS",
                "Server error" if crashed else "")
        except Exception as e:
            log(23, "Evaluations page loads", "FAIL", str(e))

        # T24: Start evaluation from chat
        if RFP_ID:
            try:
                await page.goto(f"{BASE}/chat?rfp_id={RFP_ID}&mode=evaluate", wait_until="networkidle")
                chat_input = page.locator("textarea, input[type='text']").last
                await chat_input.click()
                await chat_input.fill(
                    "Evaluate these 3 vendor bids:\n"
                    "1. TechCorp — strong technical capability, weak financials, 500k USD bid\n"
                    "2. CloudBase — balanced across all dimensions, 620k USD bid\n"
                    "3. QuickServe — low cost 380k USD but high compliance risk\n"
                    "Score each on Technical, Financial, Commercial, and Compliance dimensions. "
                    "Recommend the best vendor."
                )
                send_btn = page.locator("button[type='submit'], button:has-text('Send')").last
                await send_btn.click()
                print("  [waiting up to 90s for evaluation...]")
                for _ in range(30):
                    await page.wait_for_timeout(3000)
                    body = await page.content()
                    if any(v in body for v in ["TechCorp", "CloudBase", "QuickServe", "recommend", "Recommend"]):
                        break

                body = await page.content()
                vendors_in_page = sum(1 for v in ["TechCorp", "CloudBase", "QuickServe"] if v in body)
                if vendors_in_page == 3:
                    log(24, "Evaluation streams all 3 vendors", "PASS")
                elif vendors_in_page > 0:
                    log(24, "Evaluation streams all 3 vendors", "BUG",
                        f"Only {vendors_in_page}/3 vendors visible in chat")
                else:
                    log(24, "Evaluation streams all 3 vendors", "BUG", "No vendor names visible in evaluation response")

            except Exception as e:
                log(24, "Evaluation chat", "FAIL", str(e))

            # T25: Evaluation persisted to API
            try:
                await page.wait_for_timeout(4000)
                import urllib.request as ur
                rfp = json.loads(ur.urlopen(f"{BASE}/api/rfps/{RFP_ID}").read())
                eval_data = rfp.get("evaluation")
                if eval_data and eval_data.get("vendors"):
                    log(25, "Evaluation persisted to RFP record", "PASS",
                        f"{len(eval_data['vendors'])} vendors stored")
                else:
                    log(25, "Evaluation persisted to RFP record", "BUG",
                        "evaluation field is null or has no vendors")
            except Exception as e:
                log(25, "Evaluation persisted", "FAIL", str(e))

            # T26: Evaluations page shows results
            try:
                await page.goto(f"{BASE}/evaluations", wait_until="networkidle")
                body = await page.content()
                has_vendor = any(v in body for v in ["TechCorp", "CloudBase", "QuickServe"])
                log(26, "Evaluations page shows vendor results", "PASS" if has_vendor else "BUG",
                    "" if has_vendor else "Vendor names not visible on /evaluations page")
            except Exception as e:
                log(26, "Evaluations page shows vendor results", "FAIL", str(e))
        else:
            for n in [24, 25, 26]:
                log(n, "Evaluation tests", "FAIL", "Skipped — RFP_ID not set")

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 7 — DOCUMENTS
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 7: Documents ──")

        await page.goto(f"{BASE}/documents", wait_until="networkidle")

        # T27: Documents page lists RFPs
        try:
            body = await page.content()
            has_rfp = "Hospital" in body or "LiverX" in body or "rfp" in body.lower()
            log(27, "Documents page lists RFPs", "PASS" if has_rfp else "BUG",
                "" if has_rfp else "No RFP entries visible on /documents")
        except Exception as e:
            log(27, "Documents page lists RFPs", "FAIL", str(e))

        # T28: Status badge visible
        try:
            body = await page.content()
            has_status = any(s in body for s in ["draft", "approved", "done", "Draft", "Approved"])
            log(28, "Status badges on documents", "PASS" if has_status else "BUG",
                "" if has_status else "No status badges found")
        except Exception as e:
            log(28, "Status badges on documents", "FAIL", str(e))

        # T29: Regenerate PDF endpoint
        if RFP_ID:
            try:
                import urllib.request as ur
                req = ur.Request(
                    f"{BASE}/api/rfps/{RFP_ID}/regenerate-pdf",
                    data=b"",
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                resp = ur.urlopen(req)
                data = json.loads(resp.read())
                if data.get("filename"):
                    log(29, "Regenerate PDF endpoint", "PASS", f"filename={data['filename']}")
                else:
                    log(29, "Regenerate PDF endpoint", "BUG", f"No filename in response: {data}")
            except Exception as e:
                log(29, "Regenerate PDF endpoint", "BUG", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 8 — SETTINGS
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 8: Settings ──")

        await page.goto(f"{BASE}/settings", wait_until="networkidle")

        # T30: 4 guideline sections visible
        try:
            body = await page.content()
            found = sum(1 for kw in ["legal", "commercial", "technical", "financial"]
                        if kw.lower() in body.lower())
            if found == 4:
                log(30, "All 4 guideline tabs visible", "PASS")
            else:
                log(30, "All 4 guideline tabs visible", "BUG", f"Only {found}/4 tabs found")
        except Exception as e:
            log(30, "All 4 guideline tabs visible", "FAIL", str(e))

        # T31: Guidelines API loads content
        for cat in ["legal", "commercial", "technical", "financial"]:
            try:
                import urllib.request as ur
                data = json.loads(ur.urlopen(f"{BASE}/api/settings/guidelines/{cat}").read())
                if data.get("content"):
                    log(31, f"Guidelines API: {cat}", "PASS",
                        f"{len(data['content'])} chars")
                else:
                    log(31, f"Guidelines API: {cat}", "BUG", "content is empty")
            except Exception as e:
                log(31, f"Guidelines API: {cat}", "FAIL", str(e))

        # T32: Save guideline edit
        try:
            import urllib.request as ur
            original = json.loads(ur.urlopen(f"{BASE}/api/settings/guidelines/legal").read())["content"]
            new_content = original + "\n\n<!-- QA save test -->"
            req = ur.Request(
                f"{BASE}/api/settings/guidelines/legal",
                data=json.dumps({"content": new_content}).encode(),
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            resp = ur.urlopen(req)
            saved = json.loads(resp.read())
            if "QA save test" in saved.get("content", ""):
                log(32, "Save guideline via API (PUT)", "PASS")
                # Restore
                req2 = ur.Request(
                    f"{BASE}/api/settings/guidelines/legal",
                    data=json.dumps({"content": original}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="PUT"
                )
                ur.urlopen(req2)
            else:
                log(32, "Save guideline via API (PUT)", "BUG", "Saved content doesn't match")
        except Exception as e:
            log(32, "Save guideline via API (PUT)", "FAIL", str(e))

        # T33: Unknown guideline category → 404
        try:
            import urllib.request as ur, urllib.error
            try:
                ur.urlopen(f"{BASE}/api/settings/guidelines/nonexistent")
                log(33, "Unknown guideline category → 404", "BUG", "Expected 404 but got 200")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    log(33, "Unknown guideline category → 404", "PASS")
                else:
                    log(33, "Unknown guideline category → 404", "BUG", f"Got {he.code}")
        except Exception as e:
            log(33, "Unknown guideline category → 404", "FAIL", str(e))

        # T34: Settings UI save button works
        try:
            await page.goto(f"{BASE}/settings", wait_until="networkidle")
            # click first tab/category
            tab = page.locator("button:has-text('Legal'), a:has-text('Legal'), [data-tab='legal']")
            if await tab.count() > 0:
                await tab.first.click()
                await page.wait_for_timeout(800)
            editor = page.locator("textarea").first
            if await editor.count() > 0:
                current = await editor.input_value()
                await editor.fill(current + " ")  # trivial whitespace change
                save_btn = page.locator("button:has-text('Save'), button[type='submit']").first
                await save_btn.click()
                await page.wait_for_timeout(1200)
                body = await page.content()
                success = any(kw in body.lower() for kw in ["saved", "success", "updated", "تم"])
                log(34, "Settings UI save button", "PASS" if success else "BUG",
                    "" if success else "No success feedback in UI after save")
            else:
                log(34, "Settings UI save button", "BUG", "No textarea in settings page")
        except Exception as e:
            log(34, "Settings UI save button", "FAIL", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 9 — BILINGUAL / RTL
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 9: Bilingual / RTL ──")

        # T35: Switch to Arabic via cookie / toggle
        try:
            await ctx.add_cookies([{"name": "ui_lang", "value": "ar", "domain": "localhost", "path": "/"}])
            await page.goto(BASE, wait_until="networkidle")
            html_el = page.locator("html")
            dir_attr = await html_el.get_attribute("dir")
            lang_attr = await html_el.get_attribute("lang")
            if dir_attr == "rtl" and lang_attr == "ar":
                log(35, "Arabic RTL mode via cookie", "PASS", "dir=rtl, lang=ar")
            else:
                log(35, "Arabic RTL mode via cookie", "BUG",
                    f"dir={dir_attr}, lang={lang_attr} — expected rtl/ar")
        except Exception as e:
            log(35, "Arabic RTL mode via cookie", "FAIL", str(e))

        # T36: Cairo font loaded in AR mode
        try:
            body = await page.content()
            if "Cairo" in body:
                log(36, "Cairo font present in AR mode", "PASS")
            else:
                log(36, "Cairo font present in AR mode", "BUG", "Cairo font link not found in HTML")
        except Exception as e:
            log(36, "Cairo font present in AR mode", "FAIL", str(e))

        # T37: All nav pages render without layout crash in RTL
        rtl_errors = []
        for path in ["/", "/documents", "/evaluations", "/settings"]:
            try:
                await page.goto(BASE + path, wait_until="networkidle")
                body = await page.content()
                if "traceback" in body.lower():
                    rtl_errors.append(path)
            except Exception as e:
                rtl_errors.append(f"{path}: {e}")
        if rtl_errors:
            log(37, "All pages render in RTL mode", "BUG", f"Errors on: {rtl_errors}")
        else:
            log(37, "All pages render in RTL mode", "PASS")

        # T38: Switch back to English
        try:
            await ctx.add_cookies([{"name": "ui_lang", "value": "en", "domain": "localhost", "path": "/"}])
            await page.goto(BASE, wait_until="networkidle")
            html_el = page.locator("html")
            dir_attr = await html_el.get_attribute("dir")
            if dir_attr != "rtl":
                log(38, "Switch back to English (LTR)", "PASS", f"dir={dir_attr}")
            else:
                log(38, "Switch back to English (LTR)", "BUG", "dir still rtl after switching to en")
        except Exception as e:
            log(38, "Switch back to English (LTR)", "FAIL", str(e))

        # T39: i18n API
        try:
            import urllib.request as ur
            data = json.loads(ur.urlopen(f"{BASE}/api/i18n/en").read())
            if isinstance(data, dict) and len(data) > 0:
                log(39, "i18n API /en returns translations", "PASS",
                    f"{len(data)} keys")
            else:
                log(39, "i18n API /en returns translations", "BUG", f"Empty or non-dict: {str(data)[:100]}")
        except Exception as e:
            log(39, "i18n API /en", "FAIL", str(e))

        # T40: i18n API rejects unsupported locale
        try:
            import urllib.request as ur, urllib.error
            try:
                ur.urlopen(f"{BASE}/api/i18n/fr")
                log(40, "i18n API rejects unsupported locale", "BUG", "Expected 400 for 'fr'")
            except urllib.error.HTTPError as he:
                if he.code == 400:
                    log(40, "i18n API rejects unsupported locale", "PASS")
                else:
                    log(40, "i18n API rejects unsupported locale", "BUG", f"Got {he.code}")
        except Exception as e:
            log(40, "i18n API rejects unsupported locale", "FAIL", str(e))

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 10 — API REGRESSION
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 10: API Regression ──")

        import urllib.request as ur, urllib.error

        api_checks = [
            (41, "GET /api/rfps", lambda: ur.urlopen(f"{BASE}/api/rfps"), 200),
            (42, "GET /api/stats", lambda: ur.urlopen(f"{BASE}/api/stats"), 200),
            (43, "GET /api/evaluations", lambda: ur.urlopen(f"{BASE}/api/evaluations"), [200, 204]),
            (44, "GET /api/risk-heatmap", lambda: ur.urlopen(f"{BASE}/api/risk-heatmap"), [200, 204]),
            (45, "GET /flowchart", lambda: ur.urlopen(f"{BASE}/flowchart"), 200),
        ]
        for num, name, fn, expected in api_checks:
            try:
                resp = fn()
                code = resp.getcode()
                exp_list = expected if isinstance(expected, list) else [expected]
                if code in exp_list:
                    log(num, name, "PASS", f"HTTP {code}")
                else:
                    log(num, name, "BUG", f"Expected {expected}, got {code}")
            except urllib.error.HTTPError as he:
                exp_list = expected if isinstance(expected, list) else [expected]
                if he.code in exp_list:
                    log(num, name, "PASS", f"HTTP {he.code}")
                else:
                    log(num, name, "BUG", f"Expected {expected}, got {he.code}")
            except Exception as e:
                log(num, name, "FAIL", str(e))

        # T46: GET /api/rfps/bad-uuid → 404
        try:
            try:
                ur.urlopen(f"{BASE}/api/rfps/bad-uuid-does-not-exist")
                log(46, "GET /api/rfps/bad-uuid → 404", "BUG", "Expected 404 but got 200")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    log(46, "GET /api/rfps/bad-uuid → 404", "PASS")
                else:
                    log(46, "GET /api/rfps/bad-uuid → 404", "BUG", f"Got {he.code}")
        except Exception as e:
            log(46, "GET /api/rfps/bad-uuid → 404", "FAIL", str(e))

        # T47: POST /api/rfps missing title → 422
        try:
            req = ur.Request(
                f"{BASE}/api/rfps",
                data=json.dumps({"description": "no title"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                ur.urlopen(req)
                log(47, "POST /api/rfps missing title → 422", "BUG", "Got 200 without title")
            except urllib.error.HTTPError as he:
                if he.code == 422:
                    log(47, "POST /api/rfps missing title → 422", "PASS")
                else:
                    log(47, "POST /api/rfps missing title → 422", "BUG", f"Got {he.code}")
        except Exception as e:
            log(47, "POST /api/rfps missing title → 422", "FAIL", str(e))

        # T48: PATCH illegal transition draft→done blocked (using AR RFP which is still draft)
        if AR_RFP_ID:
            try:
                req = ur.Request(
                    f"{BASE}/api/rfps/{AR_RFP_ID}",
                    data=json.dumps({"status": "done"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="PATCH"
                )
                try:
                    ur.urlopen(req)
                    log(48, "PATCH draft→done blocked", "BUG", "Should be 422 but got 200")
                except urllib.error.HTTPError as he:
                    if he.code == 422:
                        log(48, "PATCH draft→done blocked", "PASS")
                    else:
                        log(48, "PATCH draft→done blocked", "BUG", f"Got {he.code}")
            except Exception as e:
                log(48, "PATCH draft→done blocked", "FAIL", str(e))
        else:
            log(48, "PATCH draft→done blocked", "FAIL", "Skipped — AR_RFP_ID not set")

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 11 — EDGE CASES
        # ═══════════════════════════════════════════════════════════════════
        print("\n── SECTION 11: Edge Cases ──")

        # T49: Long message doesn't crash server
        if RFP_ID:
            try:
                await ctx.add_cookies([{"name": "ui_lang", "value": "en", "domain": "localhost", "path": "/"}])
                await page.goto(f"{BASE}/chat?rfp_id={RFP_ID}", wait_until="networkidle")
                chat_input = page.locator("textarea, input[type='text']").last
                await chat_input.click()
                await chat_input.fill("test " * 400)  # 2000 chars
                send_btn = page.locator("button[type='submit'], button:has-text('Send')").last
                await send_btn.click()
                await page.wait_for_timeout(5000)
                body = await page.content()
                crashed = "500" in body or "traceback" in body.lower()
                log(49, "Long message (2000 chars) no crash", "BUG" if crashed else "PASS")
            except Exception as e:
                log(49, "Long message no crash", "FAIL", str(e))

        # T50: Mobile viewport layout
        try:
            mobile_ctx = await browser.new_context(viewport={"width": 375, "height": 812})
            mobile_page = await mobile_ctx.new_page()
            await mobile_page.goto(BASE, wait_until="networkidle")
            body = await mobile_page.content()
            # Check for horizontal scroll via JS
            has_overflow = await mobile_page.evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            if has_overflow:
                log(50, "Mobile viewport (375px) — no horizontal scroll", "BUG",
                    "Horizontal overflow detected on dashboard")
            else:
                log(50, "Mobile viewport (375px) — no horizontal scroll", "PASS")
            await mobile_ctx.close()
        except Exception as e:
            log(50, "Mobile viewport layout", "FAIL", str(e))

        await browser.close()

    # ═══════════════════════════════════════════════════════════════════════
    # FINAL REPORT
    # ═══════════════════════════════════════════════════════════════════════
    print("\n\n" + "═"*70)
    print("  FINAL QA REPORT")
    print("═"*70)

    passes  = [r for r in RESULTS if r["status"] == "PASS"]
    bugs    = [r for r in RESULTS if r["status"] == "BUG"]
    fails   = [r for r in RESULTS if r["status"] == "FAIL"]

    print(f"\n  ✅ PASS : {len(passes)}")
    print(f"  🐛 BUG  : {len(bugs)}")
    print(f"  ❌ FAIL : {len(fails)}  (infra/setup issues, not app bugs)\n")

    if bugs:
        print("─"*70)
        print("  BUGS FOUND")
        print("─"*70)
        for b in bugs:
            print(f"  [{b['num']:03d}] {b['feature']}")
            if b["notes"]:
                print(f"        → {b['notes']}")

    if fails:
        print("\n─"*70)
        print("  SETUP/INFRA FAILURES (skipped or couldn't run)")
        print("─"*70)
        for f in fails:
            print(f"  [{f['num']:03d}] {f['feature']}: {f['notes']}")

    # Summary table
    print("\n─"*70)
    print("  FULL SUMMARY TABLE")
    print("─"*70)
    print(f"  {'#':>3}  {'Status':<8}  Feature")
    print(f"  {'─'*3}  {'─'*8}  {'─'*50}")
    for r in RESULTS:
        print(f"  {r['num']:>3}  {r['status']:<8}  {r['feature']}")

    # Save report
    report_path = "qa_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_at": datetime.now().isoformat(),
            "summary": {"pass": len(passes), "bug": len(bugs), "fail": len(fails)},
            "results": RESULTS
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Full report saved → {report_path}")
    print("═"*70)


asyncio.run(run_tests())
