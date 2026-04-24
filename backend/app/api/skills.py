"""Skills API endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.skill_indexing import SkillIndexingService
from app.services.skill_suggestion import SkillSuggestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


# Pydantic models

class SkillRegistryResponse(BaseModel):
    """Skill registry entry."""
    id: str
    skill_name: str
    title: str
    description: str | None
    category: str | None
    complexity: str | None
    estimated_duration: str | None
    trigger_keywords: list[str] | None
    trigger_labels: list[str] | None
    trigger_systems: list[str] | None
    invocation_count: int
    last_invoked_at: str | None

    class Config:
        from_attributes = True


class MatchReason(BaseModel):
    """Reason for skill match."""
    type: str
    values: list[str] | None = None
    weight: float


class SuggestedSkillResponse(BaseModel):
    """Suggested skill with confidence."""
    skill: SkillRegistryResponse
    confidence: float
    match_reasons: list[MatchReason]


class SkillSuggestionsResponse(BaseModel):
    """List of skill suggestions for a context."""
    context_id: str
    suggestions: list[SuggestedSkillResponse]
    count: int


class SkillListResponse(BaseModel):
    """List of registered skills."""
    skills: list[SkillRegistryResponse]
    count: int


class IndexingStatsResponse(BaseModel):
    """Skill indexing statistics."""
    indexed: int
    updated: int
    removed: int
    errors: list[str]


class UserActionRequest(BaseModel):
    """User action on suggested skill."""
    action: str  # "accepted", "dismissed", "deferred"
    feedback: str | None = None


# API endpoints

@router.get("/contexts/{context_id}/suggested-skills", response_model=SkillSuggestionsResponse)
async def get_suggested_skills(
    context_id: UUID,
    min_confidence: float = Query(0.3, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db)
):
    """Get skill suggestions for a work context.

    Args:
        context_id: Work context UUID
        min_confidence: Minimum confidence score (0.0-1.0)
        db: Database session

    Returns:
        List of skill suggestions with confidence scores
    """
    try:
        suggestion_service = SkillSuggestionService(db)
        suggestions = await suggestion_service.suggest_skills_for_context(
            context_id,
            min_confidence
        )

        # Convert to response format
        response_suggestions = []
        for suggestion in suggestions:
            skill = suggestion["skill"]
            skill_response = SkillRegistryResponse(
                id=str(skill.id),
                skill_name=skill.skill_name,
                title=skill.title or skill.skill_name,
                description=skill.description,
                category=skill.category,
                complexity=skill.complexity,
                estimated_duration=skill.estimated_duration,
                trigger_keywords=skill.trigger_keywords,
                trigger_labels=skill.trigger_labels,
                trigger_systems=skill.trigger_systems,
                invocation_count=skill.invocation_count,
                last_invoked_at=skill.last_invoked_at.isoformat() if skill.last_invoked_at else None
            )

            match_reasons = [
                MatchReason(
                    type=reason["type"],
                    values=reason.get("values"),
                    weight=reason["weight"]
                )
                for reason in suggestion["reasons"]
            ]

            response_suggestions.append(
                SuggestedSkillResponse(
                    skill=skill_response,
                    confidence=suggestion["score"],
                    match_reasons=match_reasons
                )
            )

        return SkillSuggestionsResponse(
            context_id=str(context_id),
            suggestions=response_suggestions,
            count=len(response_suggestions)
        )

    except Exception as e:
        logger.error(f"Failed to get skill suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contexts/{context_id}/suggested-skills/{skill_id}/action")
async def record_skill_action(
    context_id: UUID,
    skill_id: UUID,
    request: UserActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Record user action on suggested skill.

    Args:
        context_id: Work context UUID
        skill_id: Skill UUID
        request: User action data
        db: Database session

    Returns:
        Status confirmation
    """
    try:
        # Validate action
        valid_actions = ["accepted", "dismissed", "deferred"]
        if request.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}"
            )

        suggestion_service = SkillSuggestionService(db)
        await suggestion_service.record_user_action(
            context_id,
            skill_id,
            request.action,
            request.feedback
        )

        return {
            "status": "recorded",
            "context_id": str(context_id),
            "skill_id": str(skill_id),
            "action": request.action
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record skill action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/registry", response_model=SkillListResponse)
async def list_skills(
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List all registered skills.

    Args:
        category: Optional category filter
        db: Database session

    Returns:
        List of all skills
    """
    try:
        skill_service = SkillIndexingService(db)
        skills = await skill_service.get_all_skills(category)

        skill_responses = [
            SkillRegistryResponse(
                id=str(skill.id),
                skill_name=skill.skill_name,
                title=skill.title or skill.skill_name,
                description=skill.description,
                category=skill.category,
                complexity=skill.complexity,
                estimated_duration=skill.estimated_duration,
                trigger_keywords=skill.trigger_keywords,
                trigger_labels=skill.trigger_labels,
                trigger_systems=skill.trigger_systems,
                invocation_count=skill.invocation_count,
                last_invoked_at=skill.last_invoked_at.isoformat() if skill.last_invoked_at else None
            )
            for skill in skills
        ]

        return SkillListResponse(
            skills=skill_responses,
            count=len(skill_responses)
        )

    except Exception as e:
        logger.error(f"Failed to list skills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex", response_model=IndexingStatsResponse)
async def reindex_skills(db: AsyncSession = Depends(get_db)):
    """Re-scan and index all skills from ~/.claude/skills/ directory.

    Args:
        db: Database session

    Returns:
        Indexing statistics
    """
    try:
        skill_service = SkillIndexingService(db)
        stats = await skill_service.index_all_skills()

        return IndexingStatsResponse(
            indexed=stats["indexed"],
            updated=stats["updated"],
            removed=stats["removed"],
            errors=stats["errors"]
        )

    except Exception as e:
        logger.error(f"Failed to reindex skills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
