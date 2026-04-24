from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_labels():
    return {
        "labels": {
            "project": [
                {"id": 1, "name": "wx", "color": "#3B82F6"},
                {"id": 2, "name": "g4", "color": "#8B5CF6"},
                {"id": 3, "name": "jobs", "color": "#F59E0B"},
                {"id": 4, "name": "temporal", "color": "#10B981"},
            ],
            "task-type": [
                {"id": 5, "name": "investigation", "color": "#EF4444"},
                {"id": 6, "name": "code-review", "color": "#6366F1"},
                {"id": 7, "name": "incident", "color": "#DC2626"},
                {"id": 8, "name": "feature", "color": "#22C55E"},
                {"id": 9, "name": "bug-fix", "color": "#F97316"},
                {"id": 10, "name": "analysis", "color": "#06B6D4"},
            ],
            "priority": [
                {"id": 11, "name": "critical", "color": "#DC2626"},
                {"id": 12, "name": "high", "color": "#F97316"},
                {"id": 13, "name": "medium", "color": "#EAB308"},
                {"id": 14, "name": "low", "color": "#6B7280"},
            ],
        }
    }


@router.post("")
async def create_label():
    return {"status": "not implemented"}


@router.put("/{label_id}")
async def update_label(label_id: int):
    return {"status": "not implemented"}


@router.delete("/{label_id}")
async def delete_label(label_id: int):
    return {"status": "not implemented"}
