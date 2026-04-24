"""Automatic entity link inference service"""
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import (
    GitBranch,
    JiraIssue,
    Agent,
    EntityLink,
    LinkType,
    LinkSourceType,
    LinkStatus,
)
from app.services.entity_link import EntityLinkService


# Product keyword → Grafana dashboard mapping
# Each entry: (keywords, dashboard_uid, dashboard_name, filter_hint)
PRODUCT_DASHBOARD_MAP = [
    # Constellations → OrdersV2 SLIs (has $item_types dropdown)
    (["skysat", "skysatscene", "skysatcollect"],
     "iqRkSMa4z", "OrdersV2 SLIs", {"item_types": "[SkySatScene]"}),
    (["pelican", "pelicanscene"],
     "iqRkSMa4z", "OrdersV2 SLIs", {"item_types": "[PelicanScene]"}),
    (["tanager", "tanagerscene", "tanagermethane", "methane"],
     "iqRkSMa4z", "OrdersV2 SLIs", {"item_types": "[TanagerScene]"}),

    # Constellations → Activation Stats (per-constellation panels)
    (["skysat", "activation"],
     "deavpes7dshdsb", "Activation Stats", {"panel": "SkySat"}),
    (["pelican", "activation"],
     "deavpes7dshdsb", "Activation Stats", {"panel": "Pelican"}),
    (["tanager", "activation"],
     "deavpes7dshdsb", "Activation Stats", {"panel": "Tanager"}),

    # G4 clusters
    (["g4c-sub", "g4 sub", "subscriptions g4"],
     "aa571e75-43ac-405a-b77e-3333bf3c6e6c", "G4 Tasks", {"cluster": "g4c-sub-*"}),
    (["g4c-live", "g4c-pioneer", "orders g4"],
     "aa571e75-43ac-405a-b77e-3333bf3c6e6c", "G4 Tasks", {"cluster": "g4c-live-03,g4c-pioneer-05"}),
    (["g4c-fusion", "fusion g4"],
     "aa571e75-43ac-405a-b77e-3333bf3c6e6c", "G4 Tasks", {"cluster": "g4c-fusion-*"}),
    (["g4c-analytics", "sif g4", "analytic feeds g4"],
     "aa571e75-43ac-405a-b77e-3333bf3c6e6c", "G4 Tasks", {"cluster": "g4c-analytics-01"}),

    # Derived products → D&D dashboards
    (["ordersv2", "orders api", "order delivery", "order stuck", "order failure"],
     "Ik8Sztf4k", "Orders API", {}),
    (["iris", "subscriptions api", "subscription delivery", "trough", "fppc"],
     "YuyRzpBVz", "Subscriptions API", {}),
    (["fair-queue", "fair queue", "fq backlog", "fq depth"],
     "bdc411a1c33a5767d31d3bcf30d8f81b23900fa4", "fair-queue", {}),
    (["ftl", "file transfer"],
     "ae5935m7ty9z4b", "FTL", {}),

    # PV products → PV dashboards
    (["forest carbon", "canopy height", "canopy cover", "aboveground carbon"],
     "deeqj9shpj8qob", "PV Backends", {"product": "forest_carbon"}),
    (["soil water", "swc"],
     "ae2bhwpd4coowd", "Field SWC/LST", {"product": "soil_water_content"}),
    (["land surface temperature", "lst"],
     "ae2bhwpd4coowd", "Field SWC/LST", {"product": "land_surface_temperature"}),
    (["biomass proxy", "crop biomass"],
     "-5JypCIVz", "Biomass Proxy", {}),

    # SIF/Analytics → Delta dashboards
    (["sif", "analytic feed", "building detection", "road detection",
      "ship detection", "vessel detection", "aircraft detection",
      "well pad", "silo bag", "change detection"],
     "aeer7ha7pemtca", "Analytics API (SIF)", {}),

    # Fusion
    (["fusion", "l3h", "cestem"],
     "aa571e75-43ac-405a-b77e-3333bf3c6e6c", "G4 Tasks", {"cluster": "g4c-fusion-*"}),
]

logger = logging.getLogger(__name__)


class LinkInferenceService:
    """Service for automatically inferring entity relationships"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.link_service = EntityLinkService(db)

    async def infer_branch_jira_links(self) -> int:
        """Infer links between branches and JIRA issues based on branch names

        Uses the linked_ticket_key_guess field populated by BranchTrackingService.

        Returns:
            int: Number of suggested links created
        """
        # Get all branches with JIRA key guesses
        result = await self.db.execute(
            select(GitBranch).where(
                GitBranch.linked_ticket_key_guess.isnot(None),
                GitBranch.linked_ticket_key_guess != ''
            )
        )
        branches = result.scalars().all()

        created_count = 0

        for branch in branches:
            jira_key = branch.linked_ticket_key_guess

            # Find matching JIRA issue in cache
            jira_result = await self.db.execute(
                select(JiraIssue).where(JiraIssue.external_key == jira_key)
            )
            jira_issue = jira_result.scalar_one_or_none()

            if not jira_issue:
                logger.debug(f"JIRA issue {jira_key} not in cache (branch: {branch.branch_name})")
                continue

            # Check if link already exists
            existing = await self._get_existing_link(
                from_type='branch',
                from_id=str(branch.id),
                to_type='jira_issue',
                to_id=str(jira_issue.id)
            )

            if existing:
                logger.debug(f"Link already exists: branch {branch.branch_name} → {jira_key}")
                continue

            # Create suggested link with high confidence (branch name is explicit)
            try:
                await self.link_service.create_link(
                    from_type='branch',
                    from_id=str(branch.id),
                    to_type='jira_issue',
                    to_id=str(jira_issue.id),
                    link_type=LinkType.IMPLEMENTS,
                    source_type=LinkSourceType.INFERRED,
                    confidence_score=0.85,  # High confidence from branch name
                    status=LinkStatus.SUGGESTED
                )
                created_count += 1
                logger.debug(f"Created suggested link: branch {branch.branch_name} → {jira_key}")
            except Exception as e:
                logger.error(f"Failed to create link for branch {branch.branch_name}: {e}")
                continue

        logger.info(f"Inferred {created_count} branch→JIRA links")
        return created_count

    async def infer_chat_jira_links(self) -> int:
        """Infer links between chats and JIRA issues based on chat.jira_key field

        Returns:
            int: Number of suggested links created
        """
        # Get all agents/chats with JIRA keys
        result = await self.db.execute(
            select(Agent).where(
                Agent.jira_key.isnot(None),
                Agent.jira_key != ''
            )
        )
        agents = result.scalars().all()

        created_count = 0

        for agent in agents:
            jira_key = agent.jira_key

            # Find matching JIRA issue in cache
            jira_result = await self.db.execute(
                select(JiraIssue).where(JiraIssue.external_key == jira_key)
            )
            jira_issue = jira_result.scalar_one_or_none()

            if not jira_issue:
                logger.debug(f"JIRA issue {jira_key} not in cache (chat: {agent.title})")
                continue

            # Check if link already exists
            existing = await self._get_existing_link(
                from_type='chat',
                from_id=str(agent.id),
                to_type='jira_issue',
                to_id=str(jira_issue.id)
            )

            if existing:
                logger.debug(f"Link already exists: chat {agent.title} → {jira_key}")
                continue

            # Create suggested link with very high confidence (explicit field)
            try:
                await self.link_service.create_link(
                    from_type='chat',
                    from_id=str(agent.id),
                    to_type='jira_issue',
                    to_id=str(jira_issue.id),
                    link_type=LinkType.DISCUSSED_IN,
                    source_type=LinkSourceType.INFERRED,
                    confidence_score=0.95,  # Very high confidence from explicit field
                    status=LinkStatus.SUGGESTED
                )
                created_count += 1
                logger.debug(f"Created suggested link: chat {agent.title} → {jira_key}")
            except Exception as e:
                logger.error(f"Failed to create link for chat {agent.title}: {e}")
                continue

        logger.info(f"Inferred {created_count} chat→JIRA links")
        return created_count

    async def infer_product_dashboard_links(self) -> int:
        """Infer links between JIRA issues and Grafana dashboards based on product keywords.

        Scans JIRA issue titles and descriptions for product/service keywords
        (e.g., "SkySat", "forest carbon", "fair-queue") and creates links to
        the relevant Grafana dashboards with filter context in metadata.

        Returns:
            int: Number of suggested links created
        """
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key.like("COMPUTE-%"))
        )
        issues = result.scalars().all()

        created_count = 0
        for issue in issues:
            text = f"{issue.summary or ''} {issue.description or ''}".lower()

            for keywords, dash_uid, dash_name, filter_hint in PRODUCT_DASHBOARD_MAP:
                if not any(kw in text for kw in keywords):
                    continue

                link_id = f"grafana-dash-{dash_uid}"

                existing = await self._get_existing_link(
                    from_type="jira_issue",
                    from_id=str(issue.id),
                    to_type="grafana_dashboard",
                    to_id=link_id,
                )
                if existing:
                    continue

                try:
                    await self.link_service.create_link(
                        from_type="jira_issue",
                        from_id=str(issue.id),
                        to_type="grafana_dashboard",
                        to_id=link_id,
                        link_type=LinkType.MONITORS_DASHBOARD,
                        source_type=LinkSourceType.INFERRED,
                        confidence_score=0.70,
                        status=LinkStatus.SUGGESTED,
                        link_metadata={
                            "dashboard_uid": dash_uid,
                            "dashboard_name": dash_name,
                            "grafana_url": f"https://planet.grafana.net/d/{dash_uid}",
                            "matched_keywords": [kw for kw in keywords if kw in text],
                            "filter_hint": filter_hint,
                        },
                    )
                    created_count += 1
                except Exception as e:
                    logger.error(f"Failed to create dashboard link for {issue.external_key}: {e}")

        logger.info(f"Inferred {created_count} JIRA→dashboard links")
        return created_count

    async def infer_all_links(self) -> dict:
        """Run all link inference heuristics

        Returns:
            dict: Results with breakdown by link type
        """
        branch_links = await self.infer_branch_jira_links()
        chat_links = await self.infer_chat_jira_links()
        dashboard_links = await self.infer_product_dashboard_links()

        total = branch_links + chat_links + dashboard_links

        return {
            "total": total,
            "branch_jira": branch_links,
            "chat_jira": chat_links,
            "product_dashboard": dashboard_links,
        }

    async def _get_existing_link(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str
    ) -> EntityLink | None:
        """Check if a link already exists between two entities

        Args:
            from_type: Source entity type
            from_id: Source entity ID
            to_type: Target entity type
            to_id: Target entity ID

        Returns:
            EntityLink if exists, None otherwise
        """
        result = await self.db.execute(
            select(EntityLink).where(
                and_(
                    EntityLink.from_type == from_type,
                    EntityLink.from_id == from_id,
                    EntityLink.to_type == to_type,
                    EntityLink.to_id == to_id
                )
            )
        )
        return result.scalar_one_or_none()
