from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

REQUIRED_TABLES = {"messages", "memories", "tool_runs", "agent_runs", "obsidian_sync_states", "schema_migrations"}


def init_db() -> None:
    """Validate database schema created by explicit migrations."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"database schema is missing required tables: {missing_list}. "
            "Run migrations first: python scripts/run_migrations.py"
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
