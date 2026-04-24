from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/search")
async def search_docs(q: str = Query(...)):
    return {"results": [], "total": 0}
