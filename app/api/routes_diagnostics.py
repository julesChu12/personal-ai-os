from fastapi import APIRouter, Request

from app.core.diagnostics import collect_diagnostics

router = APIRouter()


@router.get("/diagnostics")
def diagnostics(request: Request):
    """返回运行时依赖和配置诊断信息。"""
    scheduler = getattr(request.app.state, "scheduler", None)
    return collect_diagnostics(scheduler=scheduler)
