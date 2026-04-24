"""Summary API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List

from app.database import get_db
from app.services.chat_summary import ChatSummaryService
from app.services.context_overview import ContextOverviewService
from app.services.artifact_extraction import ArtifactExtractionService
from app.models.artifact import ArtifactType

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post("/chat/{chat_id}")
async def summarize_chat(
    chat_id: str,
    force_regenerate: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Generate or retrieve summary for a chat session."""
    summary_service = ChatSummaryService(db)

    try:
        summary = await summary_service.summarize_chat(chat_id, force_regenerate=force_regenerate)
        await db.commit()
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/{chat_id}")
async def get_chat_summary(
    chat_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str] | None:
    """Get existing summary for a chat (without generating new one)."""
    summary_service = ChatSummaryService(db)

    try:
        summary = await summary_service.get_chat_summary(chat_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context/{context_id}")
async def generate_context_overview(
    context_id: str,
    force_regenerate: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Generate or retrieve overview for a work context."""
    overview_service = ContextOverviewService(db)

    try:
        overview = await overview_service.generate_overview(context_id, force_regenerate=force_regenerate)
        await db.commit()
        return overview
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# Artifact Extraction Endpoints

@router.post("/artifacts/chat/{chat_id}")
async def extract_chat_artifacts(
    chat_id: str,
    force_reextract: bool = False,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Extract artifacts from a chat session."""
    artifact_service = ArtifactExtractionService(db)

    try:
        result = await artifact_service.extract_artifacts(chat_id, force_reextract=force_reextract)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/chat/{chat_id}")
async def get_chat_artifacts(
    chat_id: str,
    artifact_type: ArtifactType | None = Query(None),
    db: AsyncSession = Depends(get_db)
) -> List[Dict]:
    """Get artifacts for a chat session."""
    artifact_service = ArtifactExtractionService(db)

    try:
        artifacts = await artifact_service.get_artifacts(chat_id, artifact_type=artifact_type)
        return artifacts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/context/{context_id}")
async def get_context_artifacts(
    context_id: str,
    db: AsyncSession = Depends(get_db)
) -> List[Dict]:
    """Get all artifacts from all chats in a context."""
    artifact_service = ArtifactExtractionService(db)

    try:
        artifacts = await artifact_service.get_context_artifacts(context_id)
        return artifacts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
