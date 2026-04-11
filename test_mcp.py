import asyncio
from rfp_agent.mcp_bridge import slack_post_message
import os

async def main():
    print("Testing Slack MCP Configuration...")
    
    # We pass a fake channel ID to trigger a specific Slack API error
    # If we get 'channel_not_found' or 'token_expired', it means our .env token was parsed successfully!
    print("Sending message request...")
    result = await slack_post_message('C12345678', 'Hello from the ADK!')
    
    print("\n--- MCP SERVER RESPONSE ---")
    print(result)
    print("---------------------------")
    
    if "SLACK_BOT_TOKEN and SLACK_TEAM_ID must be set" in result:
        print("❌ FAILED: The tokens are STILL not loading correctly.")
    elif "channel_not_found" in result or "token_expired" in result:
        print("✅ SUCCESS: The MCP connected and authenticated with Slack (but the API returned an error because the channel/token isn't valid).")
    else:
        print("ℹ️ RESULT: Review the response above. If it's a success message, you're good to go!")

if __name__ == "__main__":
    asyncio.run(main())
