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
            print("❌ Agent not found")
            return
        
        print(f"Agent ID: {agent.id}")
        print(f"Title: {agent.title[:80]}")
        print(f"Working dir: {agent.working_directory}")
        print(f"Managed by: {agent.managed_by}")
        print(f"Session file: {agent.session_file}")

if __name__ == "__main__":
    asyncio.run(check())
