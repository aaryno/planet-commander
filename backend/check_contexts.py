import asyncio
from sqlalchemy import select, text
from app.database import async_session
from app.models import WorkContext

async def check():
    async with async_session() as db:
        # Check count
        result = await db.execute(select(WorkContext))
        contexts = result.scalars().all()
        print(f"Found {len(contexts)} work contexts")
        
        # Check database enum
        result = await db.execute(text("SELECT unnest(enum_range(NULL::origintype))"))
        enum_vals = [row[0] for row in result]
        print(f"Database origintype values: {enum_vals}")

if __name__ == "__main__":
    asyncio.run(check())
