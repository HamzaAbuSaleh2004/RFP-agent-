import os
import asyncio
from dotenv import load_dotenv
load_dotenv()
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def _invoke_mcp(command: str, args: list[str], env: dict[str, str], tool_name: str, arguments: dict) -> str:
    """Spawns an MCP server securely, calls a tool, and cleans up the sub-process."""
    # Ensure system PATH is inherited so tools like `npx` can be resolved
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
        
    server_params = StdioServerParameters(command=command, args=args, env=merged_env)
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                
                output = []
                for content in result.content:
                    if content.type == "text":
                        output.append(content.text)
                return "\n".join(output)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return f"MCP Connection Error: {str(e)}\nTraceback:\n{tb}"

# ═══════════════════════════════════════════════════════
# OFFICIALLY SUPPORTED MCP BRIDGES
# ═══════════════════════════════════════════════════════

# Slack channel routing
SLACK_LEGAL_CHANNEL   = "C0ARWKER0G4"   # Legal alerts and showstoppers
SLACK_FINANCE_CHANNEL = "C0ASMA9B33J"   # Bid rankings, budget summaries
SLACK_UPDATES_CHANNEL = "C0ASMLBU3TK"   # General progress updates


async def _slack_post(channel_id: str, text: str) -> str:
    """Internal helper — posts to a specific Slack channel via MCP."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    team  = os.environ.get("SLACK_TEAM_ID")
    if not token or not team:
        return "ERROR: SLACK_BOT_TOKEN and SLACK_TEAM_ID must be set in your .env file."

    return await _invoke_mcp(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env={"SLACK_BOT_TOKEN": token, "SLACK_TEAM_ID": team},
        tool_name="slack_post_message",
        arguments={"channel_id": channel_id, "text": text}
    )


async def slack_post_message(text: str) -> str:
    """
    Post a general progress update to the procurement updates Slack channel.
    Use for routine notifications: RFP created, evaluation started, file uploaded.
    """
    return await _slack_post(SLACK_UPDATES_CHANNEL, text)


async def slack_alert_legal(text: str) -> str:
    """
    Post an urgent legal or compliance alert to the legal Slack channel.
    Use when: sanctions hit, a showstopper compliance issue is found, legal review
    is required before proceeding, or a country/vendor triggers a hard blocker.
    The legal team monitors this channel for immediate escalation.
    """
    return await _slack_post(SLACK_LEGAL_CHANNEL, f"🚨 *Legal Alert*\n{text}")


async def slack_notify_finance(text: str) -> str:
    """
    Post a financial summary or bid ranking to the finance Slack channel.
    Use when: bid evaluation is complete (post ranking summary), budget analysis
    is done, or a vendor's financial red flag needs procurement/finance review.
    """
    return await _slack_post(SLACK_FINANCE_CHANNEL, f"💰 *Finance Update*\n{text}")

async def linear_create_issue(title: str, description: str, team_id: str) -> str:
    """Create a tracking ticket in Linear for evaluating a specific vendor bid."""
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        return "ERROR: LINEAR_API_KEY must be set in your .env file."
        
    return await _invoke_mcp(
        command="npx",
        args=["-y", "@linear/mcp-server"],
        env={"LINEAR_API_KEY": key},
        tool_name="linear_createIssue",
        arguments={"title": title, "description": description, "teamId": team_id}
    )

def gdrive_read_file(file_name: str) -> str:
    """
    Download a file from Google Drive by name and return its full text content.
    Works with Google Docs, DOCX, and PDF files.
    Use this to read and analyze the contents of any Drive document.
    """
    import tempfile
    try:
        from .drive_api import _get_service, download_file

        service = _get_service()

        # Find the file by name
        results = service.files().list(
            q=f"name contains '{file_name}' and trashed=false",
            fields="files(id, name, mimeType)",
            pageSize=5,
            orderBy="modifiedTime desc",
        ).execute()

        files = results.get("files", [])
        if not files:
            return f"No file named '{file_name}' found in Google Drive."

        file_meta = files[0]
        file_id   = file_meta["id"]
        mime      = file_meta["mimeType"]
        name      = file_meta["name"]

        # Choose export format based on mime type
        if mime == "application/vnd.google-apps.document":
            # Export Google Doc as plain text
            data = service.files().export_media(
                fileId=file_id, mimeType="text/plain"
            ).execute()
            return f"Content of '{name}':\n\n{data.decode('utf-8', errors='replace')}"

        # For DOCX and PDF, download then extract text
        suffix = ".pdf" if "pdf" in mime else ".docx"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.close()
        download_file(file_id, tmp.name)

        if suffix == ".pdf":
            import fitz
            doc  = fitz.open(tmp.name)
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()

        else:  # .docx
            import docx
            doc  = docx.Document(tmp.name)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

        os.unlink(tmp.name)

        if not text.strip():
            return f"File '{name}' was downloaded but appears to contain no readable text."

        # Cap at ~12 000 chars so the context window isn't overwhelmed
        cap = 12_000
        suffix_note = f"\n\n[Truncated — showing first {cap} characters]" if len(text) > cap else ""
        return f"Content of '{name}':\n\n{text[:cap]}{suffix_note}"

    except Exception as e:
        import traceback
        return f"Error reading file '{file_name}' from Drive: {e}\n{traceback.format_exc()}"


def gdrive_search(query: str) -> str:
    """Search Google Drive for past proposals, corporate templates, or other documents."""
    # Use the Python Drive API directly — avoids Node.js token expiry issues
    # and handles OAuth refresh automatically.
    try:
        from .drive_api import _get_service
        service = _get_service()
        results = (
            service.files()
            .list(
                q=f"fullText contains '{query}' and trashed=false",
                fields="files(id, name, mimeType, modifiedTime, webViewLink)",
                pageSize=10,
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = results.get("files", [])
        if not files:
            return f"No files found in Google Drive matching '{query}'."
        lines = [f"Found {len(files)} file(s) matching '{query}':"]
        for f in files:
            lines.append(
                f"- {f['name']} ({f['mimeType']})\n"
                f"  Link: {f.get('webViewLink', 'N/A')}\n"
                f"  Modified: {f.get('modifiedTime', 'N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        import traceback
        return f"Google Drive search error: {e}\n{traceback.format_exc()}"

# ═══════════════════════════════════════════════════════
# FIRECRAWL — Deep web reading via direct REST API
# ═══════════════════════════════════════════════════════

def _firecrawl_attempt(api_key: str, url: str, options: dict) -> tuple[bool, str]:
    """Single Firecrawl attempt. Returns (success, content_or_error)."""
    import requests
    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown"], **options},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return False, f"success=false: {data.get('error', data)}"
        content = data.get("data", {}).get("markdown", "").strip()
        if not content:
            return False, "no readable content extracted"
        cap = 15_000
        note = f"\n\n[Truncated — showing first {cap} of {len(content)} chars]" if len(content) > cap else ""
        return True, f"Scraped content from {url}:\n\n{content[:cap]}{note}"
    except Exception as e:
        return False, str(e)


async def firecrawl_scrape(url: str) -> str:
    """
    Deeply scrape a URL and return its full content as clean markdown.

    Use cases:
    - Competitor Intelligence: scrape a vendor's website to extract capabilities,
      pricing tiers, client list, and technology stack in one call.
    - Legal Compliance: crawl a country's official regulatory authority website
      (e.g. Saudi SDAIA, UK ICO, UAE TDRA) to extract the *current* rules.
    - Due Diligence: read a vendor's published case studies or certifications page.

    If the primary URL is blocked or times out, try an alternative URL for the
    same topic (e.g. IAPP, DataGuidance, or Wikipedia for regulatory summaries).
    The tool will automatically retry with more permissive settings before failing.

    Args:
        url: The full URL to scrape.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return "ERROR: FIRECRAWL_API_KEY must be set in your .env file. Sign up at firecrawl.dev."

    # Attempt 1: standard — main content only (fastest, works on most sites)
    ok, result = _firecrawl_attempt(api_key, url, {"onlyMainContent": True})
    if ok:
        return result

    first_error = result

    # Attempt 2: full page — government sites often render content outside <main>
    ok, result = _firecrawl_attempt(api_key, url, {"onlyMainContent": False})
    if ok:
        return result

    # Both attempts failed — return a soft-fail so the agent can fall back to
    # internal knowledge rather than blocking the entire workflow.
    return (
        f"SCRAPE_UNAVAILABLE: Could not retrieve live content from {url}.\n"
        f"Attempt 1 (main content): {first_error}\n"
        f"Attempt 2 (full page): {result}\n\n"
        "Fallback instruction: Use your internal knowledge for this topic, "
        "clearly note in the document that regulations were sourced from training "
        "data (cutoff August 2025) and recommend the client verify against the "
        "current official source before signing."
    )


# ═══════════════════════════════════════════════════════
# MOCK / COMMUNITY MCP BRIDGES (Pending Official URLs)
# ═══════════════════════════════════════════════════════

def notion_search_pages(query: str) -> str:
    """Retrieve templates, evaluation matrices, or past proposals from Notion."""
    key = os.environ.get("NOTION_API_KEY")
    if not key:
        return f"ERROR: NOTION_API_KEY must be set in your .env file. (Mock Search: {query})"
    return f"Retrieved Notion Corporate Template for '{query}'"

def airtable_add_vendor_record(vendor_name: str, score: int) -> str:
    """Store vendor comparison matrices and scores into Airtable."""
    return f"Mock Airtable: Vendor {vendor_name} added with score {score}."

def asana_create_task(task_name: str) -> str:
    """Create a project flow task in Asana."""
    return f"Mock Asana: Task '{task_name}' created."
