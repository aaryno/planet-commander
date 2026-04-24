import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import JiraIssue

async def check_jira():
    async with async_session() as db:
        result = await db.execute(select(JiraIssue).limit(20))
        issues = result.scalars().all()
        print(f"Found {len(issues)} JIRA issues in cache:")
        for issue in issues:
            print(f"  {issue.external_key}: {issue.title}")

if __name__ == "__main__":
    asyncio.run(check_jira())
