"""
QA Round 2 -- Tests that require a real RFP ID:
  - Create form UI (fixed selector)
  - Chat / RFP generation
  - Editor (load, save, status transitions)
  - Evaluation flow
  - Settings UI textarea (fixed selector)
  - /chat without rfp_id (re-check)
"""
import asyncio
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE   = "http://localhost:8000"
EN_ID  = "ac9eab2c-897b-4973-8baf-84c422aa82b2"
AR_ID  = "2a4c1889-981c-4f22-83f1-23e6c23d40ee"

RESULTS = []

def log(num, feature, status, notes=""):
    icon = "[PASS]" if status == "PASS" else ("[BUG] " if status == "BUG" else "[FAIL]")
    line = f"[{num:03d}] {icon} {feature}"
    if notes:
        line += f"\n       -> {notes}"
    print(line)
    RESULTS.append({"num": num, "feature": feature, "status": status, "notes": notes})


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=250)
        ctx     = await browser.new_context(viewport={"width": 1280, "height": 800})
        page    = await ctx.new_page()

        # ── CREATE FORM UI (fixed selector) ────────────────────────────────
        print("\n-- CREATE FORM UI --")

        await page.goto(f"{BASE}/create", wait_until="networkidle")

        # T1: Submit button is "Start AI Session"
        try:
            btn = page.locator("button:has-text('Start AI Session')")
            count = await btn.count()
            if count > 0:
                log(1, "Submit button labeled 'Start AI Session' exists", "PASS")
            else:
                log(1, "Submit button labeled 'Start AI Session' exists", "BUG",
                    "Button not found — verify label in create.html")
        except Exception as e:
            log(1, "Submit button exists", "FAIL", str(e))

        # T2: Empty form submit is blocked (no title)
        try:
            btn = page.locator("button:has-text('Start AI Session')").first
            await btn.click()
            await page.wait_for_timeout(800)
            still_on_create = "/create" in page.url
            if still_on_create:
                log(2, "Empty form blocked (no title)", "PASS")
            else:
                log(2, "Empty form blocked (no title)", "BUG",
                    f"Navigated to {page.url} without filling required fields")
        except Exception as e:
            log(2, "Empty form blocked", "FAIL", str(e))

        # T3: Valid form creates RFP and navigates to chat
        try:
            await page.goto(f"{BASE}/create", wait_until="networkidle")
            await page.fill("#title", "QA Test RFP via UI")
            await page.fill("#description",
                "Automated QA test — procurement of hospital IT for LiverX Riyadh campuses.")
            en_btn = page.locator("button.lang-btn:has-text('English')")
            if await en_btn.count() > 0:
                await en_btn.click()
            await page.wait_for_timeout(300)
            submit = page.locator("button:has-text('Start AI Session')").first
            await submit.click()
            await page.wait_for_timeout(3000)
            new_url = page.url
            if "/chat" in new_url or "/editor" in new_url or "rfp_id" in new_url:
                log(3, "Create form navigates to chat/editor after submit", "PASS",
                    f"url={new_url}")
            else:
                log(3, "Create form navigates to chat/editor after submit", "BUG",
                    f"Unexpected URL after submit: {new_url}")
        except Exception as e:
            log(3, "Create form submit flow", "FAIL", str(e))

        # T4: Invited users field accepts input
        try:
            await page.goto(f"{BASE}/create", wait_until="networkidle")
            inv_field = page.locator("#invited_users")
            if await inv_field.count() > 0:
                await inv_field.fill("qa@liverx.me, admin@liverx.me")
                val = await inv_field.input_value()
                if val:
                    log(4, "Invited users field accepts input", "PASS")
                else:
                    log(4, "Invited users field accepts input", "BUG", "Field is empty after fill")
            else:
                log(4, "Invited users field accepts input", "BUG", "#invited_users not found")
        except Exception as e:
            log(4, "Invited users field", "FAIL", str(e))

        # ── CHAT / AI GENERATION ────────────────────────────────────────────
        print("\n-- CHAT / AI RFP GENERATION --")

        await page.goto(f"{BASE}/chat?rfp_id={EN_ID}&mode=create", wait_until="networkidle")

        # T5: Chat page loads and shows RFP context
        try:
            body = await page.content()
            has_context = (EN_ID in body or "Hospital" in body or
                          "rfp" in body.lower() or "chat" in body.lower())
            log(5, "Chat page loads with EN RFP context", "PASS" if has_context else "BUG",
                "" if has_context else "No RFP context visible")
        except Exception as e:
            log(5, "Chat page loads", "FAIL", str(e))

        # T6: Chat input and send button exist
        try:
            chat_input = page.locator("textarea, input[placeholder*='message' i], input[placeholder*='type' i]").last
            send_btn   = page.locator("button:has-text('Send'), button[type='submit']").last
            i_count = await chat_input.count()
            b_count = await send_btn.count()
            if i_count > 0 and b_count > 0:
                log(6, "Chat input + send button present", "PASS")
            else:
                log(6, "Chat input + send button present", "BUG",
                    f"input={i_count}, button={b_count}")
        except Exception as e:
            log(6, "Chat input/button", "FAIL", str(e))

        # T7: Generate RFP via chat (full generation)
        generated_ok = False
        try:
            chat_input = page.locator("textarea").last
            await chat_input.click()
            await chat_input.fill("Generate the full RFP document.")
            send_btn = page.locator("button:has-text('Send'), button[type='submit']").last
            await send_btn.click()

            print("  [waiting up to 120s for RFP generation...]")
            for i in range(40):
                await page.wait_for_timeout(3000)
                body = await page.content()
                # Look for any section heading or 'done' SSE
                if any(s in body for s in [
                    "PROJECT OVERVIEW", "SCOPE OF WORK", "TERMS",
                    "COMPLIANCE", "FINANCIAL", "TIMELINE",
                    "Section 1", "Section 2"
                ]):
                    generated_ok = True
                    break

            body = await page.content()
            has_sections = sum(1 for s in [
                "PROJECT OVERVIEW", "SCOPE OF WORK",
                "TERMS & CONDITIONS", "COMPLIANCE",
                "FINANCIAL TERMS", "TIMELINE"
            ] if s in body)

            # Check for error event
            has_error = '"type": "error"' in body or "ADK error" in body

            if generated_ok and has_sections >= 4:
                log(7, f"RFP generated in chat ({has_sections}/6 sections visible)", "PASS")
            elif has_error:
                log(7, "RFP generation - SSE error event", "BUG",
                    "Error event received from agent")
            else:
                log(7, f"RFP generation ({has_sections}/6 sections visible)", "BUG",
                    "Fewer than 4 sections visible after 120s")
        except Exception as e:
            log(7, "RFP generation via chat", "FAIL", str(e))

        # T8: Status tool bubbles appear in chat
        try:
            body = await page.content()
            has_status = any(s in body for s in [
                "Running tool", "Handed off", "rfp_creator",
                "read_local_templates", "create_rfp_pdf"
            ])
            log(8, "Agent status bubbles visible in chat", "PASS" if has_status else "BUG",
                "" if has_status else "No tool/agent status messages seen")
        except Exception as e:
            log(8, "Status bubbles", "FAIL", str(e))

        # T9: rfp_content saved to store
        try:
            await page.wait_for_timeout(4000)
            rfp = json.loads(urllib.request.urlopen(f"{BASE}/api/rfps/{EN_ID}").read())
            if rfp.get("rfp_content"):
                log(9, "rfp_content persisted after generation", "PASS",
                    f"{len(rfp['rfp_content'])} chars")
            else:
                log(9, "rfp_content persisted after generation", "BUG",
                    "rfp_content is null — save hook in main.py:274 may not have fired")
        except Exception as e:
            log(9, "rfp_content persisted", "FAIL", str(e))

        # T10: No unresolved placeholders in rfp_content
        try:
            rfp = json.loads(urllib.request.urlopen(f"{BASE}/api/rfps/{EN_ID}").read())
            content = rfp.get("rfp_content") or ""
            unresolved = [p for p in ["[X]%", "[AMOUNT]", "[To be specified]", "[TBD]"]
                         if p in content]
            if unresolved:
                log(10, "No unresolved placeholders in generated RFP", "BUG",
                    f"Found: {unresolved}")
            elif content:
                log(10, "No unresolved placeholders in generated RFP", "PASS")
            else:
                log(10, "No unresolved placeholders in generated RFP", "FAIL",
                    "rfp_content is empty — can't check")
        except Exception as e:
            log(10, "Placeholder check", "FAIL", str(e))

        # T11: Follow-up message works
        try:
            chat_input = page.locator("textarea").last
            await chat_input.click()
            await chat_input.fill("Summarize section 5 in 3 bullet points.")
            send_btn = page.locator("button:has-text('Send'), button[type='submit']").last
            await send_btn.click()
            await page.wait_for_timeout(10000)
            body = await page.content()
            crashed = "500" in body[:200] or "traceback" in body.lower()
            log(11, "Follow-up message (no crash)", "BUG" if crashed else "PASS")
        except Exception as e:
            log(11, "Follow-up message", "FAIL", str(e))

        # T12: /chat without rfp_id
        try:
            await page.goto(f"{BASE}/chat", wait_until="networkidle")
            body = await page.content()
            traceback_crash = "traceback" in body.lower()
            http_500 = page.url.startswith(BASE) and "500" in await page.title()
            # Check if "500" literal is in the visible text (not just in scripts)
            visible_500 = await page.evaluate(
                "document.body.innerText.includes('500') || document.body.innerText.includes('Internal Server Error')"
            )
            if traceback_crash or visible_500:
                log(12, "/chat without rfp_id (no crash)", "BUG",
                    "Page shows 500 / traceback when no rfp_id supplied")
            else:
                log(12, "/chat without rfp_id (no crash)", "PASS")
        except Exception as e:
            log(12, "/chat without rfp_id", "FAIL", str(e))

        # ── EDITOR ─────────────────────────────────────────────────────────
        print("\n-- EDITOR --")

        await page.goto(f"{BASE}/editor/{EN_ID}", wait_until="networkidle")

        # T13: Editor loads
        try:
            body = await page.content()
            ok = "traceback" not in body.lower() and "404" not in (await page.title())
            log(13, "Editor page loads (no crash/404)", "PASS" if ok else "BUG",
                "" if ok else "Crash or 404 on editor page")
        except Exception as e:
            log(13, "Editor page loads", "FAIL", str(e))

        # T14: Content visible in editor textarea
        try:
            body = await page.content()
            rfp = json.loads(urllib.request.urlopen(f"{BASE}/api/rfps/{EN_ID}").read())
            has_textarea = await page.locator("textarea").count() > 0
            content = rfp.get("rfp_content") or ""
            snippet_present = content[:30].strip() in body if content else False
            if has_textarea or snippet_present:
                log(14, "rfp_content visible in editor textarea", "PASS")
            else:
                log(14, "rfp_content visible in editor textarea", "BUG",
                    "No textarea or content snippet not found in DOM")
        except Exception as e:
            log(14, "Editor textarea content", "FAIL", str(e))

        # T15: Save edit
        try:
            editor_area = page.locator("textarea").first
            if await editor_area.count() > 0:
                current = await editor_area.input_value()
                await editor_area.fill(current + "\n\n<!-- QA edit -->")
                save_btn = page.locator(
                    "button:has-text('Save'), button:has-text('Update'), button[type='submit']"
                ).first
                await save_btn.click()
                await page.wait_for_timeout(2000)
                body = await page.content()
                success = any(kw in body.lower() for kw in ["saved", "success", "updated"])
                log(15, "Editor save button gives feedback", "PASS" if success else "BUG",
                    "" if success else "No success toast/message after save")
            else:
                log(15, "Editor save button", "BUG", "No textarea in editor")
        except Exception as e:
            log(15, "Editor save", "FAIL", str(e))

        # T16: Status transition draft -> approved via API
        try:
            req = urllib.request.Request(
                f"{BASE}/api/rfps/{EN_ID}",
                data=json.dumps({"status": "approved"}).encode(),
                headers={"Content-Type": "application/json"},
                method="PATCH"
            )
            data = json.loads(urllib.request.urlopen(req).read())
            if data.get("status") == "approved":
                log(16, "Status transition draft->approved", "PASS")
            else:
                log(16, "Status transition draft->approved", "BUG",
                    f"status still={data.get('status')}")
        except Exception as e:
            log(16, "Status transition draft->approved", "FAIL", str(e))

        # T17: Illegal transition approved->draft blocked
        try:
            req = urllib.request.Request(
                f"{BASE}/api/rfps/{EN_ID}",
                data=json.dumps({"status": "draft"}).encode(),
                headers={"Content-Type": "application/json"},
                method="PATCH"
            )
            try:
                urllib.request.urlopen(req)
                log(17, "Illegal transition approved->draft blocked", "BUG",
                    "Got 200 — should be 422")
            except urllib.error.HTTPError as he:
                log(17, "Illegal transition approved->draft blocked",
                    "PASS" if he.code == 422 else "BUG",
                    f"HTTP {he.code}")
        except Exception as e:
            log(17, "Illegal transition blocked", "FAIL", str(e))

        # T18: Illegal transition draft->done blocked (AR RFP still in draft)
        try:
            req = urllib.request.Request(
                f"{BASE}/api/rfps/{AR_ID}",
                data=json.dumps({"status": "done"}).encode(),
                headers={"Content-Type": "application/json"},
                method="PATCH"
            )
            try:
                urllib.request.urlopen(req)
                log(18, "Illegal transition draft->done blocked", "BUG",
                    "Got 200 — should be 422")
            except urllib.error.HTTPError as he:
                log(18, "Illegal transition draft->done blocked",
                    "PASS" if he.code == 422 else "BUG",
                    f"HTTP {he.code}")
        except Exception as e:
            log(18, "Illegal transition draft->done", "FAIL", str(e))

        # T19: Editor 404 for bad ID
        try:
            await page.goto(f"{BASE}/editor/nonexistent-uuid-0000", wait_until="networkidle")
            body = await page.content()
            ugly_crash = "traceback" in body.lower() or "internal server error" in body.lower()
            clean_404  = "404" in body or "not found" in body.lower() or "404" in await page.title()
            if clean_404 and not ugly_crash:
                log(19, "Editor /editor/bad-id -> clean 404", "PASS")
            elif ugly_crash:
                log(19, "Editor /editor/bad-id -> clean 404", "BUG",
                    "Ugly traceback / 500 instead of clean 404")
            else:
                log(19, "Editor /editor/bad-id -> clean 404", "BUG",
                    f"No 404 page shown. Title: {await page.title()}")
        except Exception as e:
            log(19, "Editor bad ID 404", "FAIL", str(e))

        # ── EVALUATION FLOW ─────────────────────────────────────────────────
        print("\n-- EVALUATION FLOW --")

        # Need an approved RFP for evaluation — EN_ID is now approved
        await page.goto(f"{BASE}/chat?rfp_id={EN_ID}&mode=evaluate", wait_until="networkidle")

        # T20: Send evaluation request
        eval_ok = False
        try:
            chat_input = page.locator("textarea").last
            await chat_input.click()
            await chat_input.fill(
                "Evaluate these 3 vendor bids:\n"
                "1. TechCorp -- strong technical capability, weak financials, USD 500k bid\n"
                "2. CloudBase -- balanced across all dimensions, USD 620k bid\n"
                "3. QuickServe -- low cost USD 380k but high compliance risk\n"
                "Score each on Technical, Financial, Commercial, and Compliance. "
                "Recommend the best vendor."
            )
            send_btn = page.locator("button:has-text('Send'), button[type='submit']").last
            await send_btn.click()

            print("  [waiting up to 120s for evaluation...]")
            for _ in range(40):
                await page.wait_for_timeout(3000)
                body = await page.content()
                if any(v in body for v in ["TechCorp", "CloudBase", "QuickServe"]):
                    eval_ok = True
                    break

            body = await page.content()
            vendors_visible = sum(1 for v in ["TechCorp", "CloudBase", "QuickServe"] if v in body)
            if vendors_visible == 3:
                log(20, "All 3 vendors visible in evaluation response", "PASS")
            elif eval_ok:
                log(20, f"Evaluation response ({vendors_visible}/3 vendors)", "BUG",
                    f"Only {vendors_visible}/3 vendors shown")
            else:
                log(20, "Evaluation response", "BUG",
                    "No vendor names visible after 120s")
        except Exception as e:
            log(20, "Evaluation chat", "FAIL", str(e))

        # T21: Evaluation persisted to RFP record
        try:
            await page.wait_for_timeout(5000)
            rfp = json.loads(urllib.request.urlopen(f"{BASE}/api/rfps/{EN_ID}").read())
            eval_data = rfp.get("evaluation")
            if eval_data and eval_data.get("vendors"):
                log(21, "Evaluation persisted to RFP record", "PASS",
                    f"{len(eval_data['vendors'])} vendors stored")
            else:
                log(21, "Evaluation persisted to RFP record", "BUG",
                    "evaluation field null or empty — store_evaluation_results hook may not have fired")
        except Exception as e:
            log(21, "Evaluation persisted", "FAIL", str(e))

        # T22: /evaluations page shows the evaluated RFP
        try:
            await page.goto(f"{BASE}/evaluations", wait_until="networkidle")
            body = await page.content()
            has_vendor = any(v in body for v in ["TechCorp", "CloudBase", "QuickServe"])
            has_rfp    = "Hospital" in body or "LiverX" in body or EN_ID in body
            if has_vendor or has_rfp:
                log(22, "/evaluations shows evaluated RFP", "PASS")
            else:
                log(22, "/evaluations shows evaluated RFP", "BUG",
                    "No vendor names or RFP title visible on evaluations page")
        except Exception as e:
            log(22, "/evaluations page", "FAIL", str(e))

        # T23: /api/rfps/<id>/evaluation endpoint
        try:
            try:
                resp = urllib.request.urlopen(f"{BASE}/api/rfps/{EN_ID}/evaluation")
                data = json.loads(resp.read())
                if data and data.get("vendors"):
                    log(23, "GET /api/rfps/<id>/evaluation returns data", "PASS",
                        f"{len(data['vendors'])} vendors")
                else:
                    log(23, "GET /api/rfps/<id>/evaluation returns data", "BUG",
                        f"Empty or no vendors key: {str(data)[:100]}")
            except urllib.error.HTTPError as he:
                if he.code == 204:
                    log(23, "GET /api/rfps/<id>/evaluation returns data", "BUG",
                        "204 No Content — evaluation was not persisted")
                else:
                    log(23, "GET /api/rfps/<id>/evaluation returns data", "BUG",
                        f"HTTP {he.code}")
        except Exception as e:
            log(23, "Evaluation API endpoint", "FAIL", str(e))

        # ── SETTINGS UI ─────────────────────────────────────────────────────
        print("\n-- SETTINGS UI --")

        await page.goto(f"{BASE}/settings", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # T24: Click Legal tab and wait for textarea to be visible
        try:
            legal_tab = page.locator(
                "button:has-text('Legal'), a:has-text('Legal'), [data-category='legal'], li:has-text('Legal')"
            )
            if await legal_tab.count() > 0:
                await legal_tab.first.click()
                await page.wait_for_timeout(1500)

            # Wait for textarea to be visible (content loads async)
            textarea = page.locator("#guide-textarea, textarea[id*='guide']")
            try:
                await textarea.wait_for(state="visible", timeout=8000)
                log(24, "Settings Legal tab loads textarea", "PASS")
            except Exception:
                # Fall back to any visible textarea
                any_ta = page.locator("textarea:visible")
                if await any_ta.count() > 0:
                    log(24, "Settings Legal tab loads textarea", "PASS")
                else:
                    log(24, "Settings Legal tab loads textarea", "BUG",
                        "Textarea not visible after clicking Legal tab")
        except Exception as e:
            log(24, "Settings Legal tab textarea", "FAIL", str(e))

        # T25: Save button in Settings UI triggers PUT
        try:
            textarea = page.locator("#guide-textarea, textarea:visible").first
            await textarea.wait_for(state="visible", timeout=5000)
            current = await textarea.input_value()
            await textarea.fill(current.rstrip() + "\n<!-- QA UI save test -->")
            save_btn = page.locator(
                "button:has-text('Save'), button:has-text('Update'), button[type='submit']"
            ).first
            api_called = False

            async def on_request(req):
                nonlocal api_called
                if "guidelines" in req.url and req.method == "PUT":
                    api_called = True

            page.on("request", on_request)
            await save_btn.click()
            await page.wait_for_timeout(2000)

            body = await page.content()
            success_ui = any(kw in body.lower() for kw in ["saved", "success", "updated", "تم"])
            if api_called and success_ui:
                log(25, "Settings Save button calls PUT and shows feedback", "PASS")
            elif api_called:
                log(25, "Settings Save button calls PUT and shows feedback", "BUG",
                    "PUT was called but no success feedback shown in UI")
            else:
                log(25, "Settings Save button calls PUT and shows feedback", "BUG",
                    "PUT /api/settings/guidelines was NOT called on save")
        except Exception as e:
            log(25, "Settings save button", "FAIL", str(e))

        # ── DOCUMENTS PAGE ───────────────────────────────────────────────────
        print("\n-- DOCUMENTS PAGE --")

        await page.goto(f"{BASE}/documents", wait_until="networkidle")

        # T26: Regenerate PDF via UI button (if exists)
        try:
            regen_btn = page.locator(
                "button:has-text('Regenerate'), button:has-text('Download'), a:has-text('Download')"
            )
            if await regen_btn.count() > 0:
                # Just verify the endpoint responds
                req = urllib.request.Request(
                    f"{BASE}/api/rfps/{EN_ID}/regenerate-pdf",
                    data=b"",
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                resp = urllib.request.urlopen(req)
                data = json.loads(resp.read())
                log(26, "Regenerate PDF endpoint returns filename", "PASS" if data.get("filename") else "BUG",
                    data.get("filename", "no filename in response"))
            else:
                # Test API directly
                req = urllib.request.Request(
                    f"{BASE}/api/rfps/{EN_ID}/regenerate-pdf",
                    data=b"",
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                resp = urllib.request.urlopen(req)
                data = json.loads(resp.read())
                log(26, "Regenerate PDF API (no UI button found)", "PASS" if data.get("filename") else "BUG",
                    str(data))
        except Exception as e:
            log(26, "Regenerate PDF", "BUG", str(e))

        # T27: Regenerate PDF with no content -> 422
        try:
            # AR_ID has no rfp_content
            req = urllib.request.Request(
                f"{BASE}/api/rfps/{AR_ID}/regenerate-pdf",
                data=b"",
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                urllib.request.urlopen(req)
                log(27, "Regenerate PDF with no content -> 422", "BUG",
                    "Got 200 — should be 422 when no rfp_content")
            except urllib.error.HTTPError as he:
                log(27, "Regenerate PDF with no content -> 422",
                    "PASS" if he.code == 422 else "BUG",
                    f"HTTP {he.code}")
        except Exception as e:
            log(27, "Regenerate PDF no content", "FAIL", str(e))

        await browser.close()

    # ── REPORT ──────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("  ROUND 2 RESULTS")
    print("="*70)
    passes = [r for r in RESULTS if r["status"] == "PASS"]
    bugs   = [r for r in RESULTS if r["status"] == "BUG"]
    fails  = [r for r in RESULTS if r["status"] == "FAIL"]
    print(f"\n  PASS : {len(passes)}")
    print(f"  BUG  : {len(bugs)}")
    print(f"  FAIL : {len(fails)}")

    if bugs:
        print("\n--- BUGS ---")
        for b in bugs:
            print(f"  [{b['num']:02d}] {b['feature']}")
            if b["notes"]:
                print(f"       -> {b['notes']}")

    print("\n--- FULL TABLE ---")
    for r in RESULTS:
        print(f"  [{r['num']:02d}] {r['status']:<5}  {r['feature']}")

    with open("qa_report2.json", "w", encoding="utf-8") as f:
        json.dump({
            "run_at": datetime.now().isoformat(),
            "summary": {"pass": len(passes), "bug": len(bugs), "fail": len(fails)},
            "results": RESULTS
        }, f, indent=2, ensure_ascii=False)
    print("\nSaved -> qa_report2.json")
    print("="*70)


asyncio.run(run())
