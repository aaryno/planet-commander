"""Background job for automatic URL extraction from recent chats."""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as async_session_maker
from app.models import Agent
from app.services.url_extractor import URLExtractor
from app.services.url_classifier import URLClassifier
from app.services.url_handler_registry import URLHandlerRegistry

logger = logging.getLogger(__name__)


async def extract_urls_from_recent_chats(hours: int = 24):
    """Extract URLs from chats updated in the last N hours.

    Args:
        hours: Number of hours to look back (default: 24)
    """
    async with async_session_maker() as db:
        try:
            # Find chats updated recently
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            result = await db.execute(
                select(Agent)
                .where(Agent.last_active_at >= cutoff)
                .order_by(Agent.last_active_at.desc())
            )
            recent_chats = result.scalars().all()

            logger.info(f"Found {len(recent_chats)} chats updated in last {hours}h")

            if not recent_chats:
                logger.info("No recent chats to process")
                return

            # Initialize services
            url_extractor = URLExtractor(db)
            url_classifier = URLClassifier()
            url_handler_registry = URLHandlerRegistry(db)

            total_urls = 0
            total_links = 0

            # Process each chat
            for chat in recent_chats:
                try:
                    logger.info(f"Processing chat {chat.id} ({chat.title})")

                    # Extract URLs
                    extracted_urls = await url_extractor.extract_from_chat(
                        agent_id=chat.id,
                        limit_messages=100  # Only scan recent messages
                    )

                    if not extracted_urls:
                        logger.debug(f"No URLs found in chat {chat.id}")
                        continue

                    logger.info(f"Found {len(extracted_urls)} URLs in chat {chat.id}")
                    total_urls += len(extracted_urls)

                    # Classify and handle each URL
                    for url_data in extracted_urls:
                        url = url_data["url"]

                        # Classify
                        classified_url = url_classifier.classify(url)

                        # Create context
                        context = {
                            "chat_id": chat.id,
                            "message_index": url_data.get("message_index"),
                            "timestamp": url_data.get("timestamp"),
                        }

                        # Handle
                        result = await url_handler_registry.handle(
                            classified_url=classified_url,
                            context=context
                        )

                        if result.success:
                            total_links += len(result.links_created)
                            logger.debug(
                                f"Created {len(result.links_created)} links for {classified_url['type'].value}"
                            )
                        else:
                            logger.warning(
                                f"Handler failed for {url}: {result.error}"
                            )

                    # Commit after each chat
                    await db.commit()

                except Exception as e:
                    logger.error(f"Failed to process chat {chat.id}: {e}")
                    await db.rollback()
                    continue

            logger.info(
                f"URL extraction complete: {total_urls} URLs processed, "
                f"{total_links} links created from {len(recent_chats)} chats"
            )

        except Exception as e:
            logger.error(f"URL extraction job failed: {e}")
            raise


async def extract_urls_from_chat(chat_id: str):
    """Extract URLs from a specific chat (on-demand).

    Args:
        chat_id: UUID of chat to process
    """
    async with async_session_maker() as db:
        try:
            # Initialize services
            url_extractor = URLExtractor(db)
            url_classifier = URLClassifier()
            url_handler_registry = URLHandlerRegistry(db)

            logger.info(f"Extracting URLs from chat {chat_id}")

            # Extract URLs
            extracted_urls = await url_extractor.extract_from_chat(
                agent_id=chat_id
            )

            if not extracted_urls:
                logger.info(f"No URLs found in chat {chat_id}")
                return {"urls_found": 0, "links_created": 0}

            logger.info(f"Found {len(extracted_urls)} URLs in chat {chat_id}")

            total_links = 0

            # Classify and handle each URL
            for url_data in extracted_urls:
                url = url_data["url"]

                # Classify
                classified_url = url_classifier.classify(url)

                # Create context
                context = {
                    "chat_id": chat_id,
                    "message_index": url_data.get("message_index"),
                    "timestamp": url_data.get("timestamp"),
                }

                # Handle
                result = await url_handler_registry.handle(
                    classified_url=classified_url,
                    context=context
                )

                if result.success:
                    total_links += len(result.links_created)
                    logger.debug(
                        f"Created {len(result.links_created)} links for {classified_url['type'].value}"
                    )
                else:
                    logger.warning(
                        f"Handler failed for {url}: {result.error}"
                    )

            # Commit
            await db.commit()

            logger.info(
                f"URL extraction complete: {len(extracted_urls)} URLs processed, "
                f"{total_links} links created"
            )

            return {
                "urls_found": len(extracted_urls),
                "links_created": total_links
            }

        except Exception as e:
            logger.error(f"Failed to extract URLs from chat {chat_id}: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    # For manual testing
    logging.basicConfig(level=logging.INFO)
    asyncio.run(extract_urls_from_recent_chats(hours=24))
