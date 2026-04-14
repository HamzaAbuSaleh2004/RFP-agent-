import json
import logging
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env from the rfp_agent/ directory regardless of where uvicorn is launched from
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

OUTPUT_DIR = Path(__file__).parent.parent / "output"

from rfp_agent.agent import root_agent
from rfp_agent.rfp_store import create_rfp, list_rfps, get_rfp, patch_rfp
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content, Part

app = FastAPI()
templates = Jinja2Templates(directory="rfp_agent/templates")

logging.basicConfig(level=logging.DEBUG)

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


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    rfp_id: Optional[str] = None


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    rfps = list_rfps()
    return templates.TemplateResponse("dashboard.html", {"request": request, "rfps": rfps})


@app.get("/create", response_class=HTMLResponse)
async def get_create(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def get_chat(request: Request, rfp_id: Optional[str] = None):
    rfp = get_rfp(rfp_id) if rfp_id else None
    return templates.TemplateResponse(
        "rfp_creator.html",
        {"request": request, "rfp": rfp, "rfp_id": rfp_id},
    )


@app.get("/documents", response_class=HTMLResponse)
async def get_documents(request: Request):
    return templates.TemplateResponse("documents.html", {"request": request})


@app.get("/evaluations", response_class=HTMLResponse)
async def get_evaluations(request: Request):
    return templates.TemplateResponse("evaluations.html", {"request": request})


@app.get("/flowchart", response_class=HTMLResponse)
async def get_flowchart(request: Request):
    return templates.TemplateResponse("flowchart.html", {"request": request})


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

        # Wrap the plain string into the ADK Content schema
        message = Content(role="user", parts=[Part(text=user_input)])
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
    stats = {
        "active_rfps":          sum(1 for r in rfps if r["status"] == "draft"),
        "pending_evaluations":  0,
        "total_documents":      0,
    }
    eval_path = OUTPUT_DIR / "evaluations.json"
    if eval_path.exists():
        try:
            data = json.loads(eval_path.read_text(encoding="utf-8"))
            stats["pending_evaluations"] = len(data.get("vendors", []))
        except Exception:
            pass
    if OUTPUT_DIR.exists():
        stats["total_documents"] = len(list(OUTPUT_DIR.glob("*.pdf")))
    return JSONResponse(content=stats)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
