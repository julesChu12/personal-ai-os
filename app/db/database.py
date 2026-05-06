from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """初始化数据库。不再自动创建表，而是依赖外部 migration。"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if not inspector.has_table("memories"):
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Database table 'memories' not found. Please run migrations first: python scripts/run_migrations.py")
        # 在开发模式下，如果 DATABASE_URL 是 sqlite :memory:，可能需要特殊处理，
        # 但既然我们正在移除 create_all，用户应该始终显式运行迁移。



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
