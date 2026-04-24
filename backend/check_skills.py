"""Check indexed skills in database."""

import asyncio
import json

from app.database import async_session
from app.services.skill_indexing import SkillIndexingService


async def main():
    async with async_session() as db:
        service = SkillIndexingService(db)
        skills = await service.get_all_skills()

        print(f"=== All Skills ({len(skills)}) ===\n")

        for skill in skills:
            print(f"📦 {skill.skill_name}")
            print(f"   Title: {skill.title}")
            print(f"   Category: {skill.category}")
            print(f"   Complexity: {skill.complexity}")
            print(f"   Duration: {skill.estimated_duration}")
            print(f"   Labels: {skill.trigger_labels}")
            print(f"   Systems: {skill.trigger_systems}")
            print(f"   Keywords: {len(skill.trigger_keyword_list)} triggers")
            if skill.trigger_keyword_list:
                print(f"     Examples: {skill.trigger_keyword_list[:3]}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
