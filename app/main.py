from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.routes_health import router as health_router
from app.api.routes_chat import router as chat_router
from app.api.routes_memory import router as memory_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_agents import router as agents_router
from app.api.routes_openai_compat import router as openai_compat_router
from app.api.routes_diagnostics import router as diagnostics_router
from app.api.routes_scheduler import router as scheduler_router
from app.api.routes_tools import router as routes_tools_router
from app.core.errors import register_error_handlers
from app.core.request_context import register_request_context_middleware
from app.db.database import init_db
from app.scheduler.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """托管数据库初始化和后台调度器生命周期。"""
    init_db()
    app.state.scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Personal AI OS", lifespan=lifespan)
register_request_context_middleware(app)
register_error_handlers(app)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(sessions_router)
app.include_router(agents_router)
app.include_router(openai_compat_router)
app.include_router(diagnostics_router)
app.include_router(scheduler_router)
app.include_router(routes_tools_router)
