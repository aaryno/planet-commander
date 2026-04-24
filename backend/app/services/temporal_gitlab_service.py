"""Temporal GitLab service.

Fetches open MRs and pipeline status for temporal/temporalio-cloud.
"""

import asyncio
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

REPO = "temporal/temporalio-cloud"
REPO_WEB_URL = "https://hello.planet.com/code/temporal/temporalio-cloud"
GLAB_DIR = Path.home() / "tools" / "glab"
GLAB_MR = str(GLAB_DIR / "glab-mr")
GLAB_PIPELINE = str(GLAB_DIR / "glab-pipeline")
GLAB_MR_LIST = [GLAB_MR, "list", REPO, "20"]


async def _run_cmd(cmd: list[str], timeout: int = 30) -> str | None:
    """Run a command and return stdout, or None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            logger.warning("Command failed: %s -> %s", " ".join(cmd), stderr.decode("utf-8", errors="replace")[:200])
            return None
        return stdout.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        logger.warning("Command timed out: %s", " ".join(cmd))
        return None
    except FileNotFoundError:
        logger.warning("Command not found: %s", cmd[0])
        return None


def _parse_mr_list(output: str) -> list[dict]:
    """Parse glab-mr list output into structured MR data.

    Actual format:
    !99\ttemporal/temporalio-cloud!99\tUpdate tenant namespace membership\t(main) <- (koobz/update-membership)
    """
    mrs = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("Showing") or line.startswith("No "):
            continue

        # Tab-separated: !iid, repo!iid, title, branch info
        parts = line.split("\t")
        if len(parts) >= 3:
            iid_match = re.match(r"!(\d+)", parts[0])
            if iid_match:
                iid = int(iid_match.group(1))
                title = parts[2].strip()
                # Extract branch from "(main) <- (branch)" pattern
                branch = ""
                if len(parts) >= 4:
                    branch_match = re.search(r"← \((.+?)\)", parts[3])
                    if branch_match:
                        branch = branch_match.group(1)
                mrs.append({
                    "iid": iid,
                    "title": title,
                    "branch": branch,
                    "url": f"{REPO_WEB_URL}/-/merge_requests/{iid}",
                })
                continue

        # Fallback: look for !number pattern anywhere
        match = re.match(r"!(\d+)\s+(.+)", line)
        if match:
            iid = int(match.group(1))
            mrs.append({
                "iid": iid,
                "title": match.group(2).strip(),
                "branch": "",
                "url": f"{REPO_WEB_URL}/-/merge_requests/{iid}",
            })
    return mrs


async def get_open_mrs() -> dict:
    """Get open MRs for temporalio-cloud repo."""
    output = await _run_cmd(GLAB_MR_LIST)
    if output is None:
        return {"open_mrs": [], "total": 0, "error": "Failed to fetch MRs"}

    mrs = _parse_mr_list(output)

    # Also get main branch pipeline status
    pipeline_output = await _run_cmd([GLAB_PIPELINE, "status", REPO, "main"])
    main_pipeline = {"status": "unknown"}
    if pipeline_output:
        pipeline_text = pipeline_output.strip()
        if "success" in pipeline_text.lower() or "passed" in pipeline_text.lower():
            main_pipeline["status"] = "success"
        elif "failed" in pipeline_text.lower():
            main_pipeline["status"] = "failed"
        elif "running" in pipeline_text.lower():
            main_pipeline["status"] = "running"
        main_pipeline["raw"] = pipeline_text[:200]

    return {
        "open_mrs": mrs,
        "main_pipeline": main_pipeline,
        "total": len(mrs),
        "repo": REPO,
    }
