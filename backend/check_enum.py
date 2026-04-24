import asyncio
from sqlalchemy import text
from app.database import async_session

async def check_enum():
    async with async_session() as db:
        result = await db.execute(text("SELECT enum_range(NULL::origintype)"))
        enum_values = result.scalar()
        print(f"origintype enum values: {enum_values}")

if __name__ == "__main__":
    asyncio.run(check_enum())
