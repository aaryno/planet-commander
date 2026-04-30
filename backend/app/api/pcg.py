"""Planet Code Graph (PCG) REST endpoints.

Wraps the same 5 high-leverage queries that the PCG MCP server exposes,
so the Commander UI (and any other HTTP client) can use them without
shelling out to the `pcg` CLI or running a separate MCP transport.

Reuses Commander's existing async SQLAlchemy session against
`planet_ops` (the same DB PCG indexes into). Endpoints:

  GET  /api/pcg/status                        -- graph stats
  GET  /api/pcg/search?q=...&node_type=...    -- find nodes
  GET  /api/pcg/full-trace?name=...&depth=N   -- walk alert/repo/CI chain
  GET  /api/pcg/callers?func_name=...         -- function callers
  POST /api/pcg/query  body: {sql: ...}       -- read-only SELECT (capped 100 rows)

The trace logic is a port of `indexer/full_trace.py` from the PCG repo.
We don't import it directly because PCG uses sync psycopg2 and Commander
uses async SQLAlchemy — mixing the two adds complexity without value.
The walk algorithm is small enough to maintain in both places.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pcg", tags=["pcg"])


# Edge sets walked by full_trace. Mirrors indexer/full_trace.py exactly —
# if you change one, change the other.
_OUTGOING_EDGES = (
    "alert_uses_metric",
    "same_metric",
    "contains_ci_job",
    "ci_includes",
    "ci_extends",
    "ci_needs",
    "ci_triggers",
    "resolves_to_repo",
    "runs_on_runner",
    "implements_rpc",
    "deploys_chart",
)

_INCOMING_EDGES = (
    "alert_uses_metric",
    "same_metric",
    "image_built_from",
    "deploys_from_repo",
    "contains_ci_job",
    "resolves_to_repo",
    "runs_on_runner",
)


# ── Pydantic models ────────────────────────────────────────────────────


class TraceNodeOut(BaseModel):
    id: str
    node_type: str
    qualified_name: str
    short_name: str | None = None
    repo_name: str | None = None
    file_path: str | None = None


class TraceStepOut(BaseModel):
    edge_type: str | None = None
    direction: str
    depth: int
    node: TraceNodeOut
    children: list["TraceStepOut"] = Field(default_factory=list)


TraceStepOut.model_rebuild()


class FullTraceResponse(BaseModel):
    start: TraceNodeOut
    upstream: TraceStepOut
    downstream: TraceStepOut


class StatusResponse(BaseModel):
    repos: int
    nodes: int
    edges: int
    top_node_types: list[dict[str, Any]]
    top_edge_types: list[dict[str, Any]]


class SearchResultOut(BaseModel):
    id: str
    node_type: str
    qualified_name: str
    short_name: str | None = None
    repo_name: str | None = None
    file_path: str | None = None
    language: str | None = None


class CallerResultOut(BaseModel):
    id: str
    qualified_name: str
    short_name: str | None
    file_path: str | None
    repo_name: str | None


class QueryRequest(BaseModel):
    sql: str = Field(description="SELECT or WITH statement; capped to 100 rows")


# ── Helpers ────────────────────────────────────────────────────────────


def _node_to_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "node_type": row.get("node_type"),
        "qualified_name": row.get("qualified_name"),
        "short_name": row.get("short_name"),
        "repo_name": row.get("repo_name"),
        "file_path": row.get("file_path"),
    }


async def _find_start_node(db: AsyncSession, name: str) -> dict[str, Any] | None:
    # Exact match first, prefer alert > metric > pipeline > job > function > package
    sql = text(
        """
        SELECT cn.*, cr.name as repo_name
        FROM code_nodes cn JOIN code_repos cr ON cn.repo_id = cr.id
        WHERE cn.qualified_name = :name OR cn.short_name = :name
        ORDER BY
            CASE cn.node_type
                WHEN 'alert' THEN 1
                WHEN 'metric' THEN 2
                WHEN 'ci_pipeline' THEN 3
                WHEN 'ci_job' THEN 4
                WHEN 'function' THEN 5
                WHEN 'package' THEN 6
                ELSE 9
            END
        LIMIT 1
        """
    )
    result = await db.execute(sql, {"name": name})
    row = result.mappings().first()
    if row:
        return dict(row)

    # Fuzzy fallback
    sql2 = text(
        """
        SELECT cn.*, cr.name as repo_name
        FROM code_nodes cn JOIN code_repos cr ON cn.repo_id = cr.id
        WHERE cn.qualified_name ILIKE :pat OR cn.short_name ILIKE :pat
        ORDER BY
            CASE cn.node_type
                WHEN 'alert' THEN 1
                WHEN 'metric' THEN 2
                WHEN 'ci_pipeline' THEN 3
                ELSE 9
            END,
            length(cn.qualified_name)
        LIMIT 1
        """
    )
    result = await db.execute(sql2, {"pat": f"%{name}%"})
    row = result.mappings().first()
    return dict(row) if row else None


async def _neighbors(
    db: AsyncSession,
    node_id: Any,
    direction: str,
    edges: tuple[str, ...],
) -> list[dict[str, Any]]:
    if direction == "out":
        sql = text(
            """
            SELECT cn.*, cr.name as repo_name, ce.edge_type
            FROM code_edges ce
            JOIN code_nodes cn ON cn.id = ce.to_node_id
            JOIN code_repos cr ON cr.id = cn.repo_id
            WHERE ce.from_node_id = :nid AND ce.edge_type = ANY(:edges)
            ORDER BY ce.edge_type, cn.qualified_name
            """
        )
    else:
        sql = text(
            """
            SELECT cn.*, cr.name as repo_name, ce.edge_type
            FROM code_edges ce
            JOIN code_nodes cn ON cn.id = ce.from_node_id
            JOIN code_repos cr ON cr.id = cn.repo_id
            WHERE ce.to_node_id = :nid AND ce.edge_type = ANY(:edges)
            ORDER BY ce.edge_type, cn.qualified_name
            """
        )
    result = await db.execute(sql, {"nid": node_id, "edges": list(edges)})
    return [dict(r) for r in result.mappings().all()]


async def _walk(
    db: AsyncSession,
    parent_step: dict[str, Any],
    direction: str,
    edges: tuple[str, ...],
    max_depth: int,
    visited: set[Any],
    fanout_limit: int,
) -> None:
    """Recursive BFS extending parent_step['children']."""
    if parent_step["depth"] >= max_depth:
        return
    pairs = await _neighbors(db, int(parent_step["node"]["id"]), direction, edges)
    if len(pairs) > fanout_limit:
        truncated_count = len(pairs) - fanout_limit
        pairs = pairs[:fanout_limit]
    else:
        truncated_count = 0
    for row in pairs:
        if row["id"] in visited:
            continue
        visited.add(row["id"])
        child = {
            "edge_type": row["edge_type"],
            "direction": direction,
            "depth": parent_step["depth"] + 1,
            "node": _node_to_out(row),
            "children": [],
        }
        parent_step["children"].append(child)
        await _walk(db, child, direction, edges, max_depth, visited, fanout_limit)
    if truncated_count:
        parent_step["children"].append(
            {
                "edge_type": None,
                "direction": direction,
                "depth": parent_step["depth"] + 1,
                "node": {
                    "id": f"truncated::{parent_step['node']['id']}::{direction}",
                    "node_type": "_truncated",
                    "qualified_name": f"... and {truncated_count} more",
                    "short_name": None,
                    "repo_name": None,
                    "file_path": None,
                },
                "children": [],
            }
        )


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/status", response_model=StatusResponse)
async def status(db: AsyncSession = Depends(get_db)) -> StatusResponse:
    """Graph summary stats."""
    repos = (await db.execute(text("SELECT count(*)::int as n FROM code_repos"))).scalar_one()
    nodes = (await db.execute(text("SELECT count(*)::int as n FROM code_nodes"))).scalar_one()
    edges = (await db.execute(text("SELECT count(*)::int as n FROM code_edges"))).scalar_one()
    top_nodes = await db.execute(
        text(
            "SELECT node_type, count(*)::int as n FROM code_nodes "
            "GROUP BY node_type ORDER BY n DESC LIMIT 25"
        )
    )
    top_edges = await db.execute(
        text(
            "SELECT edge_type, count(*)::int as n FROM code_edges "
            "GROUP BY edge_type ORDER BY n DESC LIMIT 25"
        )
    )
    return StatusResponse(
        repos=repos,
        nodes=nodes,
        edges=edges,
        top_node_types=[dict(r) for r in top_nodes.mappings().all()],
        top_edge_types=[dict(r) for r in top_edges.mappings().all()],
    )


@router.get("/search", response_model=list[SearchResultOut])
async def search(
    q: str = Query(..., min_length=1, description="Search term"),
    node_type: str | None = Query(None, description="Filter by node_type"),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResultOut]:
    """Find nodes by name (qualified_name or short_name ILIKE)."""
    params: dict[str, Any] = {"pat": f"%{q}%", "lim": limit}
    where = "(cn.qualified_name ILIKE :pat OR cn.short_name ILIKE :pat)"
    if node_type:
        where += " AND cn.node_type = :nt"
        params["nt"] = node_type
    sql = text(
        f"""
        SELECT cn.id, cn.node_type, cn.qualified_name, cn.short_name,
               cn.file_path, cn.language, cr.name as repo_name
        FROM code_nodes cn JOIN code_repos cr ON cr.id = cn.repo_id
        WHERE {where}
        ORDER BY length(cn.qualified_name)
        LIMIT :lim
        """
    )
    result = await db.execute(sql, params)
    return [
        SearchResultOut(
            id=str(r["id"]),
            node_type=r["node_type"],
            qualified_name=r["qualified_name"],
            short_name=r.get("short_name"),
            repo_name=r.get("repo_name"),
            file_path=r.get("file_path"),
            language=r.get("language"),
        )
        for r in result.mappings().all()
    ]


@router.get("/callers", response_model=list[CallerResultOut])
async def callers(
    func_name: str = Query(..., min_length=1),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[CallerResultOut]:
    """Find callers of a function via the `calls` edge type."""
    sql = text(
        """
        SELECT DISTINCT cn_from.id, cn_from.qualified_name, cn_from.short_name,
               cn_from.file_path, cr.name as repo_name
        FROM code_edges ce
        JOIN code_nodes cn_to ON cn_to.id = ce.to_node_id
        JOIN code_nodes cn_from ON cn_from.id = ce.from_node_id
        JOIN code_repos cr ON cr.id = cn_from.repo_id
        WHERE ce.edge_type = 'calls'
          AND (cn_to.short_name = :name OR cn_to.qualified_name = :name)
        LIMIT :lim
        """
    )
    result = await db.execute(sql, {"name": func_name, "lim": limit})
    return [
        CallerResultOut(
            id=str(r["id"]),
            qualified_name=r["qualified_name"],
            short_name=r.get("short_name"),
            file_path=r.get("file_path"),
            repo_name=r.get("repo_name"),
        )
        for r in result.mappings().all()
    ]


@router.get("/full-trace", response_model=FullTraceResponse)
async def full_trace(
    name: str = Query(..., min_length=1, description="Node identifier"),
    depth: int = Query(6, ge=1, le=10),
    fanout: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> FullTraceResponse:
    """Walk the alert/metric/repo → CI → runner → workload chain.

    Mirrors `pcg full-trace` (and the MCP `pcg_full_trace` tool). Returns
    a tree of upstream and downstream nodes.
    """
    start = await _find_start_node(db, name)
    if start is None:
        raise HTTPException(status_code=404, detail=f"No node found matching '{name}'")

    start_node_dict = _node_to_out(start)
    upstream_root = {
        "edge_type": None,
        "direction": "root",
        "depth": 0,
        "node": start_node_dict,
        "children": [],
    }
    downstream_root = {
        "edge_type": None,
        "direction": "root",
        "depth": 0,
        "node": start_node_dict,
        "children": [],
    }

    visited_up: set[Any] = {start["id"]}
    visited_down: set[Any] = {start["id"]}

    await _walk(db, upstream_root, "in", _INCOMING_EDGES, depth, visited_up, fanout)
    await _walk(db, downstream_root, "out", _OUTGOING_EDGES, depth, visited_down, fanout)

    return FullTraceResponse(
        start=TraceNodeOut(**start_node_dict),
        upstream=TraceStepOut(**upstream_root),
        downstream=TraceStepOut(**downstream_root),
    )


_FORBIDDEN_KEYWORDS = (
    "INSERT ", "UPDATE ", "DELETE ", "DROP ",
    "ALTER ", "TRUNCATE ", "GRANT ", "REVOKE ",
)


@router.post("/query")
async def query(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Execute a read-only SELECT/WITH against the graph. Capped to 100 rows.

    Defense-in-depth: must start with SELECT or WITH, must not contain any
    of the forbidden keywords (INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/
    GRANT/REVOKE). The DB role itself may have write perms, so the
    application-level check matters.
    """
    sql_text = (req.sql or "").strip()
    head = sql_text.lstrip("(").upper()
    if not (head.startswith("SELECT") or head.startswith("WITH")):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT and WITH queries are allowed.",
        )
    upper = sql_text.upper()
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in upper:
            raise HTTPException(
                status_code=400,
                detail=f"Forbidden keyword in query: {kw.strip()}",
            )

    try:
        result = await db.execute(text(sql_text))
    except Exception as exc:  # SQL error
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc

    rows = result.mappings().all()
    # Coerce non-JSON-serializable types
    out: list[dict[str, Any]] = []
    for r in rows[:100]:
        coerced: dict[str, Any] = {}
        for k, v in dict(r).items():
            if hasattr(v, "isoformat"):
                coerced[k] = v.isoformat()
            elif isinstance(v, (int, float, str, bool, type(None), dict, list)):
                coerced[k] = v
            else:
                coerced[k] = str(v)
        out.append(coerced)
    return out
