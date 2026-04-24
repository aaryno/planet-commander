"""Test script for skill suggestion service."""

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from app.database import async_session
from app.models import WorkContext, JiraIssue, SkillRegistry
from app.services.skill_suggestion import SkillSuggestionService

logging.basicConfig(level=logging.INFO)


async def main():
    async with async_session() as db:
        # Create a test JIRA issue
        jira_issue = JiraIssue(
            external_key="COMPUTE-1234",
            title="WX task failed with OOM in podrunner",
            description="Task task-01ABC123 failed. Seeing OOM kills in kubectl logs. Need to investigate.",
            labels=["wx", "incident"],  # Will be stored as JSONB
            status="In Progress",
            url="https://jira.example.com/browse/COMPUTE-1234",
            source_last_synced_at=datetime.utcnow(),
        )
        db.add(jira_issue)
        await db.flush()

        # Create a test work context
        context = WorkContext(
            title="Debug WX task OOM failure",
            slug="compute-1234-wx-task-oom",
            origin_type="jira",  # OriginType enum value
            primary_jira_issue_id=jira_issue.id,
            status="active",  # ContextStatus enum value
            health_status="yellow",  # HealthStatus enum value
        )
        db.add(context)
        await db.flush()

        print(f"\n=== Created Test Context ===")
        print(f"Context ID: {context.id}")
        print(f"JIRA: {jira_issue.external_key}")
        print(f"Labels: {jira_issue.labels}")
        print(f"Description: {jira_issue.description[:100]}...")

        # Get suggestions
        suggestion_service = SkillSuggestionService(db)
        suggestions = await suggestion_service.suggest_skills_for_context(
            context.id,
            min_confidence=0.3
        )

        print(f"\n=== Skill Suggestions ({len(suggestions)}) ===")
        for i, suggestion in enumerate(suggestions, 1):
            skill = suggestion["skill"]
            print(f"\n{i}. {skill.skill_name}")
            print(f"   Confidence: {suggestion['score']:.2f} ({int(suggestion['score'] * 100)}%)")
            print(f"   Category: {skill.category}")
            print(f"   Complexity: {skill.complexity}")
            print(f"   Duration: {skill.estimated_duration}")
            print(f"   Match reasons:")
            for reason in suggestion["reasons"]:
                print(f"     - {reason['type']}: {reason.get('values', [])} (weight: {reason['weight']:.2f})")

        # Test recording user action
        if suggestions:
            top_skill = suggestions[0]["skill"]
            print(f"\n=== Recording User Action ===")
            print(f"User accepted: {top_skill.skill_name}")

            await suggestion_service.record_user_action(
                context.id,
                top_skill.id,
                "accepted",
                "This skill helped identify the OOM issue"
            )

            # Check if invocation count increased
            result = await db.execute(
                select(SkillRegistry).where(SkillRegistry.id == top_skill.id)
            )
            updated_skill = result.scalar_one()
            print(f"Invocation count: {updated_skill.invocation_count}")

        # Clean up
        await db.rollback()  # Don't save test data
        print("\n=== Test Complete (rolled back) ===")


if __name__ == "__main__":
    asyncio.run(main())
