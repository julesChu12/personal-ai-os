from fastapi import APIRouter

router = APIRouter()


@router.get("/agents")
def agents():
    return {
        "agents": ["planner", "researcher", "coder", "executor", "memory_agent"],
        "note": "MVP agents are placeholders. Extend app/agents for real workflows.",
    }
