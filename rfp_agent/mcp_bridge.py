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

async def slack_post_message(channel_id: str, text: str) -> str:
    """Post an RFP draft or notification message directly to a Slack channel."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    team = os.environ.get("SLACK_TEAM_ID")
    if not token or not team:
        return "ERROR: SLACK_BOT_TOKEN and SLACK_TEAM_ID must be set in your .env file."
        
    return await _invoke_mcp(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env={"SLACK_BOT_TOKEN": token, "SLACK_TEAM_ID": team},
        tool_name="slack_post_message",
        arguments={"channel_id": channel_id, "text": text}
    )

async def linear_create_issue(title: str, description: str, team_id: str) -> str:
    """Create a tracking ticket in Linear for evaluating a specific vendor bid."""
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        return "ERROR: LINEAR_API_KEY must be set in your .env file."
        
    return await _invoke_mcp(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-linear"],
        env={"LINEAR_API_KEY": key},
        tool_name="linear_create_issue",
        arguments={"title": title, "description": description, "teamId": team_id}
    )

async def gdrive_search(query: str) -> str:
    """Search Google Drive for past proposals, corporate templates, or other documents."""
    # Absolute paths are required for the gdrive MCP
    base_dir = r"c:\Users\hamza\Desktop\LiverX\RFP"
    oauth_path = os.path.join(base_dir, "credentials.json")
    
    # Check if the user really provided the file
    if not os.path.exists(oauth_path):
        return "ERROR: credentials.json not found in the RFP directory."

    # The server uses these environment variables to handle tokens cleanly
    env = {
        "GDRIVE_OAUTH_PATH": oauth_path,
        "GDRIVE_CREDENTIALS_PATH": os.path.join(base_dir, ".gdrive-token.json")
    }

    # The MCP tool name for searching files in the official server is 'gdrive_search'
    return await _invoke_mcp(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-gdrive"],
        env=env,
        tool_name="gdrive_search",
        arguments={"query": query}
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
