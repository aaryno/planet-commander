import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import Agent

async def check_agents():
    async with async_session() as db:
        result = await db.execute(select(Agent).limit(5))
        agents = result.scalars().all()
        print(f"Found {len(agents)} agents:")
        for agent in agents:
            print(f"  ID: {agent.id}, Title: {agent.title}, JIRA: {agent.jira_key}, Project: {agent.project}")

if __name__ == "__main__":
    asyncio.run(check_agents())
