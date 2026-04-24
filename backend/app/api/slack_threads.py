"""Slack threads API endpoints."""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.slack_thread import SlackThread
from app.models.jira_issue import JiraIssue
from app.services.slack_thread_service import SlackThreadService
from app.services.jira_cache import JiraCacheService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack/threads", tags=["slack-threads"])


# Request Models

class ParseSlackUrlRequest(BaseModel):
    """Request to parse a single Slack URL."""
    slack_url: str = Field(..., description="Slack thread URL")
    include_surrounding: bool = Field(False, description="Include ±24h context")


class RefreshThreadRequest(BaseModel):
    """Request to refresh a thread from Slack."""
    include_surrounding: bool = Field(False, description="Include ±24h context")


# Response Models

class SlackThreadResponse(BaseModel):
    """Slack thread response model."""
    id: str
    channel_id: str
    channel_name: Optional[str]
    thread_ts: str
    permalink: str

    # Metadata
    participant_count: Optional[int]
    message_count: Optional[int]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_hours: Optional[float]

    # Summary
    summary_id: Optional[str]
    title: Optional[str]
    summary_text: Optional[str]

    # Context flags
    is_incident: bool
    severity: Optional[str]
    incident_type: Optional[str]
    surrounding_context_fetched: bool

    # Cross-references
    jira_keys: Optional[List[str]]
    pagerduty_incident_ids: Optional[List[str]]
    gitlab_mr_refs: Optional[List[str]]
    cross_channel_refs: Optional[List[str]]

    # Tracking
    fetched_at: datetime
    last_updated_at: datetime

    # Computed properties
    is_active: bool
    has_cross_references: bool
    duration_display: str
    reference_count: int

    @classmethod
    def from_model(cls, thread: SlackThread):
        """Convert SlackThread model to response."""
        return cls(
            id=str(thread.id),
            channel_id=thread.channel_id,
            channel_name=thread.channel_name,
            thread_ts=thread.thread_ts,
            permalink=thread.permalink,
            participant_count=thread.participant_count,
            message_count=thread.message_count,
            start_time=thread.start_time,
            end_time=thread.end_time,
            duration_hours=thread.duration_hours,
            summary_id=str(thread.summary_id) if thread.summary_id else None,
            title=thread.title,
            summary_text=thread.summary_text,
            is_incident=thread.is_incident,
            severity=thread.severity,
            incident_type=thread.incident_type,
            surrounding_context_fetched=thread.surrounding_context_fetched,
            jira_keys=thread.jira_key_list,
            pagerduty_incident_ids=thread.pagerduty_incident_list,
            gitlab_mr_refs=thread.gitlab_mr_list,
            cross_channel_refs=thread.channel_ref_list,
            fetched_at=thread.fetched_at,
            last_updated_at=thread.last_updated_at,
            is_active=thread.is_active,
            has_cross_references=thread.has_cross_references,
            duration_display=thread.duration_display,
            reference_count=thread.reference_count,
        )

    class Config:
        from_attributes = True


class SlackThreadDetailResponse(SlackThreadResponse):
    """Detailed Slack thread with messages."""
    messages: Optional[List[Dict]]
    participants: Optional[List[Dict]]
    reactions: Optional[Dict]


class SlackThreadListResponse(BaseModel):
    """List of Slack threads."""
    threads: List[SlackThreadResponse]
    total: int


class ParseJiraResponse(BaseModel):
    """Response from parsing JIRA ticket for Slack links."""
    jira_key: str
    threads_found: int
    threads_synced: int
    threads: List[SlackThreadResponse]


class ParseUrlResponse(BaseModel):
    """Response from parsing a single Slack URL."""
    thread: SlackThreadResponse
    newly_created: bool


# Endpoints

@router.post("/parse-jira/{jira_key}", response_model=ParseJiraResponse)
async def parse_jira_ticket(
    jira_key: str,
    include_surrounding: bool = Query(False, description="Include ±24h context"),
    db: AsyncSession = Depends(get_db)
):
    """Scan JIRA ticket for Slack links and parse all threads.

    Fetches the JIRA ticket, extracts Slack URLs from description and comments,
    then fetches and caches all referenced threads.

    Args:
        jira_key: JIRA issue key (e.g., COMPUTE-1234)
        include_surrounding: If True, fetch ±24h context for each thread

    Returns:
        ParseJiraResponse with synced threads
    """
    try:
        # Initialize services
        jira_cache = JiraCacheService(db)
        slack_service = SlackThreadService(db)

        # Fetch JIRA issue from cache/API
        try:
            jira_issue = await jira_cache.sync_issue_to_cache(jira_key)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Combine description and comments for scanning
        text = jira_issue.description or ""
        # TODO: In future, also scan JIRA comments if available in cache

        # Parse and sync all Slack threads
        threads = await slack_service.parse_and_sync_from_text(
            text,
            include_surrounding=include_surrounding
        )

        logger.info(f"Parsed JIRA {jira_key}: found {len(threads)} Slack threads")

        return ParseJiraResponse(
            jira_key=jira_key,
            threads_found=len(threads),
            threads_synced=len(threads),
            threads=[SlackThreadResponse.from_model(t) for t in threads]
        )

    except Exception as e:
        logger.error(f"Error parsing JIRA {jira_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse-url", response_model=ParseUrlResponse)
async def parse_slack_url(
    request: ParseSlackUrlRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Parse a single Slack thread URL.

    Fetches the thread from Slack API and caches it locally.

    Args:
        request: ParseSlackUrlRequest with URL and options

    Returns:
        ParseUrlResponse with synced thread
    """
    try:
        slack_service = SlackThreadService(db)

        # Check if already cached
        existing = await slack_service.get_thread_by_url(request.slack_url)
        newly_created = existing is None

        # Parse and sync
        threads = await slack_service.parse_and_sync_from_text(
            request.slack_url,
            include_surrounding=request.include_surrounding
        )

        if not threads:
            raise HTTPException(
                status_code=400,
                detail="No valid Slack URL found in provided text"
            )

        thread = threads[0]
        logger.info(f"Parsed Slack URL: {request.slack_url} (new={newly_created})")

        return ParseUrlResponse(
            thread=SlackThreadResponse.from_model(thread),
            newly_created=newly_created
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing Slack URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads", response_model=SlackThreadListResponse)
async def list_threads(
    channel_id: Optional[str] = Query(None, description="Filter by channel"),
    is_incident: Optional[bool] = Query(None, description="Filter incident threads"),
    has_jira_key: Optional[str] = Query(None, description="Filter by JIRA key"),
    since_days: Optional[int] = Query(7, description="Filter threads from last N days"),
    limit: int = Query(50, le=500, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """List Slack threads with filters.

    Returns threads sorted by start_time (most recent first).

    Args:
        channel_id: Filter by Slack channel ID
        is_incident: Filter incident-flagged threads
        has_jira_key: Filter threads mentioning this JIRA key
        since_days: Only include threads from last N days
        limit: Maximum number of results

    Returns:
        SlackThreadListResponse with filtered threads
    """
    try:
        slack_service = SlackThreadService(db)

        # Calculate since datetime
        since = None
        if since_days:
            from datetime import timedelta, timezone
            since = datetime.now(timezone.utc) - timedelta(days=since_days)

        # Search threads
        threads = await slack_service.search_threads(
            channel_id=channel_id,
            is_incident=is_incident,
            has_jira_key=has_jira_key,
            since=since,
            limit=limit
        )

        return SlackThreadListResponse(
            threads=[SlackThreadResponse.from_model(t) for t in threads],
            total=len(threads)
        )

    except Exception as e:
        logger.error(f"Error listing threads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}", response_model=SlackThreadDetailResponse)
async def get_thread(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed thread info including messages.

    Returns full thread data with messages, participants, and reactions.

    Args:
        thread_id: Thread UUID

    Returns:
        SlackThreadDetailResponse with full data
    """
    try:
        # Fetch thread
        result = await db.execute(
            select(SlackThread).where(SlackThread.id == thread_id)
        )
        thread = result.scalar_one_or_none()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        return SlackThreadDetailResponse(
            id=str(thread.id),
            channel_id=thread.channel_id,
            channel_name=thread.channel_name,
            thread_ts=thread.thread_ts,
            permalink=thread.permalink,
            participant_count=thread.participant_count,
            message_count=thread.message_count,
            start_time=thread.start_time,
            end_time=thread.end_time,
            duration_hours=thread.duration_hours,
            summary_id=str(thread.summary_id) if thread.summary_id else None,
            title=thread.title,
            summary_text=thread.summary_text,
            is_incident=thread.is_incident,
            severity=thread.severity,
            incident_type=thread.incident_type,
            surrounding_context_fetched=thread.surrounding_context_fetched,
            jira_keys=thread.jira_key_list,
            pagerduty_incident_ids=thread.pagerduty_incident_list,
            gitlab_mr_refs=thread.gitlab_mr_list,
            cross_channel_refs=thread.channel_ref_list,
            fetched_at=thread.fetched_at,
            last_updated_at=thread.last_updated_at,
            is_active=thread.is_active,
            has_cross_references=thread.has_cross_references,
            duration_display=thread.duration_display,
            reference_count=thread.reference_count,
            messages=thread.messages,
            participants=thread.participants,
            reactions=thread.reactions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{thread_id}/refresh", response_model=SlackThreadResponse)
async def refresh_thread(
    thread_id: UUID,
    request: RefreshThreadRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Re-fetch thread from Slack API.

    Updates the cached thread with latest data from Slack.

    Args:
        thread_id: Thread UUID
        request: RefreshThreadRequest with options

    Returns:
        SlackThreadResponse with updated data
    """
    try:
        # Fetch existing thread
        result = await db.execute(
            select(SlackThread).where(SlackThread.id == thread_id)
        )
        thread = result.scalar_one_or_none()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Re-fetch from Slack
        slack_service = SlackThreadService(db)

        thread_data = await slack_service.fetch_thread(
            thread.channel_id,
            thread.thread_ts,
            include_surrounding=request.include_surrounding
        )

        # Sync to database
        updated_thread = await slack_service.sync_thread(thread_data)

        logger.info(f"Refreshed Slack thread {thread_id}")

        return SlackThreadResponse.from_model(updated_thread)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/by-jira/{jira_key}", response_model=SlackThreadListResponse)
async def get_threads_by_jira(
    jira_key: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all threads linked to a JIRA ticket.

    Searches for threads that mention the JIRA key in their messages.

    Args:
        jira_key: JIRA issue key (e.g., COMPUTE-1234)

    Returns:
        SlackThreadListResponse with matching threads
    """
    try:
        slack_service = SlackThreadService(db)

        # Search by JIRA key
        threads = await slack_service.search_threads(
            has_jira_key=jira_key.upper(),
            limit=100
        )

        return SlackThreadListResponse(
            threads=[SlackThreadResponse.from_model(t) for t in threads],
            total=len(threads)
        )

    except Exception as e:
        logger.error(f"Error fetching threads for JIRA {jira_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
