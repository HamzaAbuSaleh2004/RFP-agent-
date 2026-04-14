import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env from the rfp_agent/ directory regardless of where uvicorn is launched from
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

OUTPUT_DIR      = Path(__file__).parent.parent / "output"
TEMPLATES_DIR   = Path(__file__).parent.parent / "company_templates"

# Map URL category slug → filename stem in company_templates/
GUIDELINE_FILES = {
    "legal":      "legal_guidelines.md",
    "commercial": "commercial_guidelines.md",
    "technical":  "technical_guidelines.md",
    "financial":  "financial_guidelines.md",
}

from rfp_agent.agent import root_agent
from rfp_agent.rfp_store import create_rfp, list_rfps, get_rfp, patch_rfp
from rfp_agent.i18n import t, is_rtl, get_locale_from_cookie, all_translations, SUPPORTED_LOCALES
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content, Part

app = FastAPI()
templates = Jinja2Templates(directory="rfp_agent/templates")

# Expose the translation helper directly inside every Jinja2 template
templates.env.globals["t"]      = t
templates.env.globals["is_rtl"] = is_rtl

logging.basicConfig(level=logging.DEBUG)


# ── i18n helper ───────────────────────────────────────────────────────────────

def _locale(request: Request) -> str:
    """Read the ui_lang cookie; fall back to 'en'."""
    return get_locale_from_cookie(request.headers.get("cookie"))

# Initialize once so session memory persists across requests
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name="rfp_agent", session_service=session_service)


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class CreateRFPRequest(BaseModel):
    title: str
    description: str
    language: str = "en"
    created_by: str = "user"
    invited_users: List[str] = []


class PatchRFPRequest(BaseModel):
    status: Optional[str] = None
    rfp_content: Optional[str] = None
    assigned_vendor: Optional[str] = None
    invited_users: Optional[List[str]] = None


class GuidelineUpdateRequest(BaseModel):
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    rfp_id: Optional[str] = None


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    locale = _locale(request)
    rfps   = list_rfps()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "rfps": rfps,
        "locale": locale, "rtl": is_rtl(locale),
    })


@app.get("/create", response_class=HTMLResponse)
async def get_create(request: Request):
    locale = _locale(request)
    return templates.TemplateResponse("create.html", {
        "request": request, "locale": locale, "rtl": is_rtl(locale),
    })


@app.get("/chat", response_class=HTMLResponse)
async def get_chat(request: Request, rfp_id: Optional[str] = None, mode: Optional[str] = None):
    locale = _locale(request)
    rfp    = get_rfp(rfp_id) if rfp_id else None
    return templates.TemplateResponse("rfp_creator.html", {
        "request": request, "rfp": rfp, "rfp_id": rfp_id,
        "mode": mode or "create",
        "locale": locale, "rtl": is_rtl(locale),
    })


@app.get("/documents", response_class=HTMLResponse)
async def get_documents(request: Request):
    locale = _locale(request)
    rfps   = list_rfps()
    return templates.TemplateResponse("documents.html", {
        "request": request, "locale": locale, "rtl": is_rtl(locale), "rfps": rfps,
    })


@app.get("/evaluations", response_class=HTMLResponse)
async def get_evaluations(request: Request):
    locale = _locale(request)
    rfps   = list_rfps()
    return templates.TemplateResponse("evaluations.html", {
        "request": request, "locale": locale, "rtl": is_rtl(locale), "rfps": rfps,
    })


@app.get("/flowchart", response_class=HTMLResponse)
async def get_flowchart(request: Request):
    locale = _locale(request)
    return templates.TemplateResponse("flowchart.html", {
        "request": request, "locale": locale, "rtl": is_rtl(locale),
    })


# ── RFP CRUD endpoints ────────────────────────────────────────────────────────

@app.post("/api/rfps")
async def api_create_rfp(body: CreateRFPRequest):
    record = create_rfp(
        title=body.title,
        description=body.description,
        language=body.language,
        created_by=body.created_by,
        invited_users=body.invited_users,
    )
    return JSONResponse(content=record, status_code=201)


@app.get("/api/rfps")
async def api_list_rfps():
    return JSONResponse(content=list_rfps())


@app.get("/api/rfps/{rfp_id}")
async def api_get_rfp(rfp_id: str):
    rfp = get_rfp(rfp_id)
    if rfp is None:
        raise HTTPException(status_code=404, detail="RFP not found")
    return JSONResponse(content=rfp)


@app.patch("/api/rfps/{rfp_id}")
async def api_patch_rfp(rfp_id: str, body: PatchRFPRequest):
    updates = body.model_dump(exclude_none=True)
    try:
        updated = patch_rfp(rfp_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail="RFP not found")
    return JSONResponse(content=updated)


@app.get("/api/rfps/{rfp_id}/evaluation")
async def api_get_rfp_evaluation(rfp_id: str):
    """Return the evaluation data stored inside a specific RFP record."""
    rfp = get_rfp(rfp_id)
    if rfp is None:
        raise HTTPException(status_code=404, detail="RFP not found")
    evaluation = rfp.get("evaluation")
    if evaluation is None:
        return JSONResponse(content=None, status_code=204)
    return JSONResponse(content=evaluation)


@app.get("/api/rfps/{rfp_id}/risk-heatmap")
async def api_get_rfp_risk_heatmap(rfp_id: str):
    """Return the risk heatmap stored inside a specific RFP record."""
    rfp = get_rfp(rfp_id)
    if rfp is None:
        raise HTTPException(status_code=404, detail="RFP not found")
    heatmap = rfp.get("risk_heatmap")
    if heatmap is None:
        return JSONResponse(content=None, status_code=204)
    return JSONResponse(content=heatmap)


# ── Chat / SSE endpoint ───────────────────────────────────────────────────────

@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    user_input = body.message
    session_id = body.session_id
    rfp_id     = body.rfp_id

    async def event_generator():
        # Ensure the session exists — ADK 1.x does not auto-create sessions.
        existing = await session_service.get_session(
            app_name="rfp_agent", user_id="user1", session_id=session_id
        )
        if existing is None:
            await session_service.create_session(
                app_name="rfp_agent", user_id="user1", session_id=session_id
            )

        # When the RFP is in Arabic, prepend a language directive on the very
        # first message of each session so every sub-agent inherits the context.
        effective_input = user_input
        if rfp_id:
            rfp_record = get_rfp(rfp_id)
            if rfp_record and rfp_record.get("language") == "ar" and existing is None:
                effective_input = (
                    "[LANGUAGE DIRECTIVE — MANDATORY]\n"
                    "You MUST conduct this entire conversation in Arabic "
                    "(Modern Standard Arabic / اللغة العربية الفصحى). "
                    "Draft all RFP content, section headings, clauses, and responses in formal Arabic. "
                    "Use proper right-to-left formatting conventions. "
                    "Every TEXT response you write must be in Arabic.\n"
                    "CRITICAL EXCEPTION: Function/tool calls (transfer_to_agent, read_local_templates, "
                    "create_rfp_pdf, fmp_get_financials, etc.) are technical JSON operations — they are "
                    "ALWAYS called using their English names. This does NOT violate the Arabic rule. "
                    "You MUST still call functions normally whenever the routing rules require it.\n\n"
                    + user_input
                )

        # Wrap the plain string into the ADK Content schema
        message = Content(role="user", parts=[Part(text=effective_input)])
        try:
            async for event in runner.run_async(
                user_id="user1",
                session_id=session_id,
                new_message=message,
            ):
                # ── Debug: log event structure ───────────────────────────────
                author = getattr(event, "author", None)
                logging.debug(
                    "ADK event | author=%s | has_content=%s | "
                    "parts=%s | is_final=%s",
                    author,
                    event.content is not None,
                    (
                        [(type(p).__name__, bool(getattr(p, "text", None)))
                         for p in event.content.parts]
                        if event.content and event.content.parts else "none"
                    ),
                    event.is_final_response() if hasattr(event, "is_final_response") else "n/a",
                )

                # ── Tool calls ───────────────────────────────────────────────
                try:
                    fn_calls = event.get_function_calls()
                except Exception:
                    fn_calls = []
                if fn_calls:
                    for call in fn_calls:
                        yield f"data: {json.dumps({'type': 'status', 'text': f'Running tool: {call.name}'})}\n\n"

                        # When create_rfp_pdf fires and we have an rfp_id,
                        # capture the markdown and persist it to the store.
                        if call.name == "create_rfp_pdf" and rfp_id:
                            try:
                                args = call.args if isinstance(call.args, dict) else {}
                                content_md = args.get("rfp_content")
                                if content_md:
                                    patch_rfp(rfp_id, {"rfp_content": content_md})
                                    logging.info(
                                        "Saved rfp_content to RFP %s (%d chars)",
                                        rfp_id, len(content_md),
                                    )
                            except Exception as save_err:
                                logging.warning("Could not save rfp_content: %s", save_err)

                        # When store_evaluation_results fires and we have an rfp_id,
                        # persist the evaluation to the correct RFP record.
                        if call.name == "store_evaluation_results" and rfp_id:
                            try:
                                args = call.args if isinstance(call.args, dict) else {}
                                results_json = args.get("results_json", "")
                                if results_json:
                                    eval_data = json.loads(results_json)
                                    patch_rfp(rfp_id, {"evaluation": eval_data})
                                    logging.info(
                                        "Saved evaluation to RFP %s (%d vendors)",
                                        rfp_id, len(eval_data.get("vendors", [])),
                                    )
                            except Exception as save_err:
                                logging.warning("Could not save evaluation to RFP: %s", save_err)

                        # When risk_heatmap fires and we have an rfp_id,
                        # persist the heatmap to the correct RFP record.
                        if call.name == "risk_heatmap" and rfp_id:
                            try:
                                args = call.args if isinstance(call.args, dict) else {}
                                compliance_json = args.get("compliance_results", "")
                                if compliance_json:
                                    # The tool already computes and saves; we also
                                    # grab its output later. But pre-save the raw
                                    # result via the tool's rfp_id param.
                                    logging.info(
                                        "risk_heatmap tool called for RFP %s", rfp_id
                                    )
                            except Exception as save_err:
                                logging.warning("Could not handle risk_heatmap: %s", save_err)

                # ── Agent transfers ──────────────────────────────────────────
                if author and author != root_agent.name:
                    yield f"data: {json.dumps({'type': 'status', 'text': f'Handed off to: {author}'})}\n\n"

                # ── Text chunks (streaming partial tokens) ───────────────────
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        text = getattr(part, "text", None)
                        if text:
                            yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"

                # ── Final response fallback ──────────────────────────────────
                elif (
                    hasattr(event, "is_final_response")
                    and event.is_final_response()
                    and event.content
                ):
                    for part in (event.content.parts or []):
                        text = getattr(part, "text", None)
                        if text:
                            yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logging.error("Error in chat stream", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Existing data endpoints ───────────────────────────────────────────────────

@app.get("/api/evaluations")
async def api_get_evaluations():
    path = OUTPUT_DIR / "evaluations.json"
    if not path.exists():
        return JSONResponse(content=None, status_code=204)
    try:
        return JSONResponse(content=json.loads(path.read_text(encoding="utf-8")))
    except Exception as e:
        logging.error("Failed to read evaluations.json", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/risk-heatmap")
async def api_get_risk_heatmap():
    path = OUTPUT_DIR / "risk_heatmap.json"
    if not path.exists():
        return JSONResponse(content=None, status_code=204)
    try:
        return JSONResponse(content=json.loads(path.read_text(encoding="utf-8")))
    except Exception as e:
        logging.error("Failed to read risk_heatmap.json", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/stats")
async def api_get_stats():
    rfps = list_rfps()
    # Count evaluations stored inside RFP records
    evaluated_rfps = [r for r in rfps if r.get("evaluation") is not None]
    total_vendors_evaluated = sum(
        len(r["evaluation"].get("vendors", []))
        for r in evaluated_rfps
    )
    stats = {
        "active_rfps":          sum(1 for r in rfps if r["status"] == "draft"),
        "pending_evaluations":  total_vendors_evaluated,
        "total_documents":      0,
    }
    if OUTPUT_DIR.exists():
        stats["total_documents"] = len(list(OUTPUT_DIR.glob("*.pdf")))
    return JSONResponse(content=stats)


# ── Settings page ─────────────────────────────────────────────────────────────

@app.get("/settings", response_class=HTMLResponse)
async def get_settings(request: Request):
    locale = _locale(request)
    return templates.TemplateResponse("settings.html", {
        "request": request, "locale": locale, "rtl": is_rtl(locale),
    })


# ── Editor page ───────────────────────────────────────────────────────────────

@app.get("/editor/{rfp_id}", response_class=HTMLResponse)
async def get_editor(request: Request, rfp_id: str):
    rfp = get_rfp(rfp_id)
    if rfp is None:
        raise HTTPException(status_code=404, detail="RFP not found")
    locale = _locale(request)
    return templates.TemplateResponse("editor.html", {
        "request": request, "rfp": rfp,
        "locale": locale, "rtl": is_rtl(locale),
    })


# ── i18n API ─────────────────────────────────────────────────────────────────

@app.get("/api/i18n/{locale}")
async def api_i18n(locale: str):
    if locale not in SUPPORTED_LOCALES:
        raise HTTPException(status_code=400, detail=f"Unsupported locale '{locale}'. Use: {SUPPORTED_LOCALES}")
    return JSONResponse(content=all_translations(locale))


# ── Guidelines API ────────────────────────────────────────────────────────────

def _guideline_record(category: str) -> dict:
    """Read one guideline file and return a serialisable record."""
    filename = GUIDELINE_FILES[category]
    path     = TEMPLATES_DIR / filename
    if not path.exists():
        content = ""
        last_modified = None
    else:
        content = path.read_text(encoding="utf-8")
        mtime   = path.stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return {
        "category":      category,
        "filename":      filename,
        "content":       content,
        "last_modified": last_modified,
    }


@app.get("/api/settings/guidelines")
async def api_get_all_guidelines():
    return JSONResponse(content=[_guideline_record(c) for c in GUIDELINE_FILES])


@app.get("/api/settings/guidelines/{category}")
async def api_get_guideline(category: str):
    if category not in GUIDELINE_FILES:
        raise HTTPException(status_code=404, detail=f"Unknown category '{category}'")
    return JSONResponse(content=_guideline_record(category))


@app.put("/api/settings/guidelines/{category}")
async def api_put_guideline(category: str, body: GuidelineUpdateRequest):
    if category not in GUIDELINE_FILES:
        raise HTTPException(status_code=404, detail=f"Unknown category '{category}'")
    path = TEMPLATES_DIR / GUIDELINE_FILES[category]
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    logging.info("Guideline '%s' updated (%d chars)", category, len(body.content))
    return JSONResponse(content=_guideline_record(category))


# ── Regenerate PDF endpoint ───────────────────────────────────────────────────

@app.post("/api/rfps/{rfp_id}/regenerate-pdf")
async def api_regenerate_pdf(rfp_id: str):
    rfp = get_rfp(rfp_id)
    if rfp is None:
        raise HTTPException(status_code=404, detail="RFP not found")
    content = rfp.get("rfp_content")
    if not content:
        raise HTTPException(status_code=422, detail="No rfp_content to render")

    from rfp_agent.custom_tools import create_rfp_pdf as _create_pdf
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in rfp["title"])[:60]
    filename   = f"{safe_title.replace(' ', '_')}_regenerated.pdf"

    result = _create_pdf(rfp_content=content, output_filename=filename)
    return JSONResponse(content={"result": result, "filename": filename})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
