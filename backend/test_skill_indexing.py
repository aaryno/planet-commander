"""Test script for skill indexing."""

import asyncio
import logging

from app.database import async_session
from app.services.skill_indexing import SkillIndexingService

logging.basicConfig(level=logging.INFO)


async def main():
    async with async_session() as db:
        service = SkillIndexingService(db)
        stats = await service.index_all_skills()

        print("\n=== Skill Indexing Results ===")
        print(f"New skills indexed: {stats['indexed']}")
        print(f"Skills updated: {stats['updated']}")
        print(f"Skills removed: {stats['removed']}")
        print(f"Errors: {len(stats['errors'])}")

        if stats['errors']:
            print("\nErrors:")
            for error in stats['errors']:
                print(f"  - {error}")

        # List all skills
        skills = await service.get_all_skills()
        print(f"\n=== Total Skills: {len(skills)} ===")
        for skill in skills[:5]:  # Show first 5
            print(f"\n{skill.skill_name}:")
            print(f"  Category: {skill.category}")
            print(f"  Labels: {skill.trigger_labels}")
            print(f"  Systems: {skill.trigger_systems}")
            print(f"  Keywords: {len(skill.trigger_keyword_list)} triggers")


if __name__ == "__main__":
    asyncio.run(main())
