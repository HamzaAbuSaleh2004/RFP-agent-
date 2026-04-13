import os
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

def _read_single_file(file_name: str) -> str:
    """Internal: fetch one Drive file by name and return its text content."""
    import tempfile
    try:
        from .drive_api import _get_service, download_file

        service = _get_service()
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

        if mime == "application/vnd.google-apps.document":
            data = service.files().export_media(
                fileId=file_id, mimeType="text/plain"
            ).execute()
            return f"Content of '{name}':\n\n{data.decode('utf-8', errors='replace')}"

        suffix = ".pdf" if "pdf" in mime else ".docx"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.close()
        download_file(file_id, tmp.name, known_mime=mime)  # skip extra metadata GET

        if suffix == ".pdf":
            import fitz
            doc  = fitz.open(tmp.name)
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
        else:
            import docx
            doc  = docx.Document(tmp.name)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

        os.unlink(tmp.name)

        if not text.strip():
            return f"File '{name}' was downloaded but appears to contain no readable text."

        cap = 12_000
        note = f"\n\n[Truncated — showing first {cap} characters]" if len(text) > cap else ""
        return f"Content of '{name}':\n\n{text[:cap]}{note}"

    except Exception as e:
        import traceback
        return f"Error reading '{file_name}' from Drive: {e}\n{traceback.format_exc()}"


def gdrive_read_file(file_name: str) -> str:
    """
    Download a file from Google Drive by name and return its full text content.
    Works with Google Docs, DOCX, and PDF files.
    """
    return _read_single_file(file_name)



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
# MOCK / COMMUNITY MCP BRIDGES (Pending Official URLs)
# ═══════════════════════════════════════════════════════

def airtable_add_vendor_record(vendor_name: str, score: int) -> str:
    """Store vendor comparison matrices and scores into Airtable."""
    return f"Mock Airtable: Vendor {vendor_name} added with score {score}."
