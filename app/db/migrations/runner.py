from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import Column, DateTime, MetaData, String, Table, func, inspect, select
from sqlalchemy.engine import Engine

from app.db.migrations.versions import MIGRATION_MODULES


SCHEMA_MIGRATIONS_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    revision: str
    description: str
    upgrade: Callable[[Any], None]


def load_migrations() -> list[Migration]:
    return [
        Migration(
            revision=module.revision,
            description=module.description,
            upgrade=module.upgrade,
        )
        for module in MIGRATION_MODULES
    ]


def apply_migrations(engine: Engine, migrations: list[Migration] | None = None) -> dict[str, Any]:
    migrations = migrations or load_migrations()
    applied_now: list[str] = []

    with engine.begin() as connection:
        migration_table = _ensure_schema_migrations_table(connection)
        applied_revisions = _get_applied_revisions(connection, migration_table)

        for migration in migrations:
            if migration.revision in applied_revisions:
                continue
            migration.upgrade(connection)
            connection.execute(
                migration_table.insert().values(
                    revision=migration.revision,
                    description=migration.description,
                )
            )
            applied_revisions.add(migration.revision)
            applied_now.append(migration.revision)

    return {
        "status": "ok",
        "applied": applied_now,
        "pending": [],
    }


def get_migration_status(engine: Engine, migrations: list[Migration] | None = None) -> dict[str, Any]:
    migrations = migrations or load_migrations()
    all_revisions = [migration.revision for migration in migrations]
    inspector = inspect(engine)
    if SCHEMA_MIGRATIONS_TABLE not in inspector.get_table_names():
        return {
            "status": "pending" if all_revisions else "ok",
            "applied": [],
            "pending": all_revisions,
        }

    with engine.begin() as connection:
        migration_table = _schema_migrations_table()
        applied_revisions = _get_applied_revisions(connection, migration_table)

    pending = [revision for revision in all_revisions if revision not in applied_revisions]
    return {
        "status": "ok" if not pending else "pending",
        "applied": [revision for revision in all_revisions if revision in applied_revisions],
        "pending": pending,
    }


def _schema_migrations_table() -> Table:
    metadata = MetaData()
    return Table(
        SCHEMA_MIGRATIONS_TABLE,
        metadata,
        Column("revision", String(255), primary_key=True),
        Column("description", String(255), nullable=False),
        Column("applied_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


def _ensure_schema_migrations_table(connection: Any) -> Table:
    table = _schema_migrations_table()
    table.create(bind=connection, checkfirst=True)
    return table


def _get_applied_revisions(connection: Any, migration_table: Table) -> set[str]:
    return set(connection.execute(select(migration_table.c.revision)).scalars().all())
