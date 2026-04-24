import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import Agent

async def check():
    async with async_session() as db:
        result = await db.execute(
            select(Agent).where(Agent.id == "5201e739-5f49-439d-af90-abad3fd63f2c")
        )
        agent = result.scalar_one_or_none()
        
        if not agent:
            print("❌ Agent not found in database")
            return
        
        print(f"✅ Agent found:")
        print(f"   Title: {agent.title}")
        print(f"   Project: {agent.project}")
        print(f"   JIRA key: {agent.jira_key}")
        print(f"   Git branch: {agent.git_branch}")
        print(f"   First prompt: {agent.first_prompt[:100] if agent.first_prompt else 'None'}...")
        print(f"   Message count: {agent.message_count}")

if __name__ == "__main__":
    asyncio.run(check())
