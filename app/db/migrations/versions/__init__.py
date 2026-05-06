from app.db.migrations.versions import (
    v0001_initial_schema,
    v0002_tool_runs,
    v0003_agent_runs,
    v0004_obsidian_sync_states,
)


MIGRATION_MODULES = [
    v0001_initial_schema,
    v0002_tool_runs,
    v0003_agent_runs,
    v0004_obsidian_sync_states,
]
