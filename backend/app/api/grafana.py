from fastapi import APIRouter

router = APIRouter()


@router.get("/traffic/{project}")
async def get_traffic(project: str):
    return {"project": project, "level": "unknown", "data": []}


@router.get("/workloads")
async def get_workloads():
    return {"workloads": []}


@router.get("/trends/{project}")
async def get_trends(project: str, period: str = "mom"):
    return {"project": project, "period": period, "data": []}
