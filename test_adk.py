import asyncio
from google.adk import Runner
from rfp_agent.agent import root_agent

async def main():
    runner = Runner(agent=root_agent)
    async for event in runner.run_async(user_id='test', session_id='1', new_message='say hi'):
        print(type(event))

asyncio.run(main())
