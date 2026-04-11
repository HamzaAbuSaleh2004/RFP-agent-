import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the rfp_agent/ directory regardless of where uvicorn is launched from
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from rfp_agent.agent import root_agent
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content, Part

app = FastAPI()
templates = Jinja2Templates(directory="rfp_agent/templates")

logging.basicConfig(level=logging.INFO)

# Initialize once so session memory persists across requests
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name="rfp_agent", session_service=session_service)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def get_chat(request: Request):
    return templates.TemplateResponse("rfp_creator.html", {"request": request})

@app.get("/documents", response_class=HTMLResponse)
async def get_documents(request: Request):
    return templates.TemplateResponse("documents.html", {"request": request})

@app.get("/evaluations", response_class=HTMLResponse)
async def get_evaluations(request: Request):
    return templates.TemplateResponse("evaluations.html", {"request": request})


@app.post("/api/chat")
async def api_chat(request: Request):
    data = await request.json()
    user_input = data.get("message", "")
    session_id = data.get("session_id", "default_session")

    async def event_generator():
        # Ensure the session exists — ADK 1.x does not auto-create sessions.
        # get_session returns None (not an exception) when missing.
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
                # ── Text chunks ──────────────────────────────────────────────
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            yield f"data: {json.dumps({'type': 'chunk', 'text': part.text})}\n\n"

                # ── Tool calls ───────────────────────────────────────────────
                if event.get_function_calls():
                    for call in event.get_function_calls():
                        yield f"data: {json.dumps({'type': 'status', 'text': f'Running tool: {call.name}'})}\n\n"

                # ── Agent transfers ──────────────────────────────────────────
                if hasattr(event, "author") and event.author and event.author != root_agent.name:
                    yield f"data: {json.dumps({'type': 'status', 'text': f'Handed off to: {event.author}'})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logging.error("Error in chat stream", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
