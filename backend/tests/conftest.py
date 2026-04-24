"""
Pytest configuration and fixtures for tests.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.base import Base


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for pytest-asyncio."""
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Create a test database session for each test.

    Uses existing database with data cleanup for isolation.
    """
    # Create test engine
    engine = create_async_engine(settings.database_url, echo=False)

    # Create session
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Clean up test data before test
        await session.execute(text("TRUNCATE TABLE warning_events CASCADE"))
        await session.execute(text("TRUNCATE TABLE warning_escalation_metrics CASCADE"))
        await session.execute(text("TRUNCATE TABLE work_contexts CASCADE"))
        await session.execute(text("TRUNCATE TABLE investigation_artifacts CASCADE"))
        await session.execute(text("TRUNCATE TABLE grafana_alert_definitions CASCADE"))
        await session.execute(text("TRUNCATE TABLE entity_links CASCADE"))
        await session.commit()

        yield session

        # Clean up after test
        await session.rollback()
        await session.execute(text("TRUNCATE TABLE warning_events CASCADE"))
        await session.execute(text("TRUNCATE TABLE warning_escalation_metrics CASCADE"))
        await session.execute(text("TRUNCATE TABLE work_contexts CASCADE"))
        await session.execute(text("TRUNCATE TABLE investigation_artifacts CASCADE"))
        await session.execute(text("TRUNCATE TABLE grafana_alert_definitions CASCADE"))
        await session.execute(text("TRUNCATE TABLE entity_links CASCADE"))
        await session.commit()

    # Dispose engine
    await engine.dispose()
