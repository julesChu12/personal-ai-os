from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Memory, ObsidianSyncState
from app.memory.obsidian_sync import ObsidianSyncEngine, memory_content_hash


class FakeVectorStore:
    calls = []

    def upsert_memory(self, text, payload, point_id=None):
        self.calls.append({"text": text, "payload": payload, "point_id": point_id})
        return point_id or f"point-{payload['title']}"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clear_fake_vector_store():
    FakeVectorStore.calls = []


def write_note(path: Path, title: str, content: str, memory_type: str = "learning", importance: int = 5) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n"
        f"title: \"{title}\"\n"
        f"type: {memory_type}\n"
        f"tags: [sync]\n"
        f"importance: {importance}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"## Summary\n{content}\n",
        encoding="utf-8",
    )
    return path


def add_memory(db, title: str, content: str, path: Path | None = None, user_id: str = "u1", project_id: str = "p1"):
    memory = Memory(
        user_id=user_id,
        project_id=project_id,
        session_id="s1",
        memory_type="learning",
        title=title,
        content=content,
        tags=["sync"],
        importance=5,
        obsidian_path=str(path.resolve()) if path else None,
        qdrant_point_id=f"point-{title}",
    )
    db.add(memory)
    db.flush()
    return memory


def add_state(db, memory: Memory, path: Path, file_hash: str | None = None, memory_hash: str | None = None):
    state = ObsidianSyncState(
        memory_id=memory.id,
        user_id=memory.user_id,
        project_id=memory.project_id,
        obsidian_path=str(path.resolve()),
        file_hash=file_hash or memory_content_hash(memory),
        memory_hash=memory_hash or memory_content_hash(memory),
        status="ok",
    )
    db.add(state)
    db.flush()
    return state


def test_dry_run_classifies_all_sync_states_without_side_effects(db, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    unchanged_path = write_note(vault / "unchanged.md", "unchanged", "same")
    unchanged = add_memory(db, "unchanged", "same", unchanged_path)
    add_state(db, unchanged, unchanged_path)

    write_note(vault / "vault_only.md", "vault_only", "from vault")

    add_memory(db, "db_only", "from db")

    vault_changed_path = write_note(vault / "vault_changed.md", "vault_changed", "old")
    vault_changed = add_memory(db, "vault_changed", "old", vault_changed_path)
    add_state(db, vault_changed, vault_changed_path)
    write_note(vault_changed_path, "vault_changed", "new from vault")

    db_changed_path = write_note(vault / "db_changed.md", "db_changed", "old")
    db_changed = add_memory(db, "db_changed", "old", db_changed_path)
    add_state(db, db_changed, db_changed_path)
    db_changed.content = "new from db"

    both_path = write_note(vault / "both_changed.md", "both_changed", "old")
    both = add_memory(db, "both_changed", "old", both_path)
    add_state(db, both, both_path)
    both.content = "new from db"
    write_note(both_path, "both_changed", "new from vault")

    deleted_path = write_note(vault / "deleted.md", "deleted", "old")
    deleted = add_memory(db, "deleted", "old", deleted_path)
    add_state(db, deleted, deleted_path)
    deleted_path.unlink()

    outside_path = tmp_path / "outside.md"
    add_memory(db, "outside", "content", outside_path)
    db.commit()

    report = ObsidianSyncEngine(str(vault), vector_store_factory=FakeVectorStore).dry_run(db, "u1", "p1")

    states = report["summary"]["states"]
    assert states["unchanged"] == 1
    assert states["vault_only"] == 1
    assert states["db_only"] == 1
    assert states["vault_changed"] == 1
    assert states["db_changed"] == 1
    assert states["both_changed"] == 1
    assert states["vault_deleted"] == 1
    assert states["path_missing"] == 1
    assert report["summary"]["conflicts"] == 1
    assert db.query(ObsidianSyncState).count() == 5
    assert FakeVectorStore.calls == []


def test_apply_vault_changed_updates_existing_memory_and_vector(db, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    path = write_note(vault / "topic.md", "topic", "old")
    memory = add_memory(db, "topic", "old", path)
    add_state(db, memory, path)
    db.commit()

    write_note(path, "topic", "new from vault")

    report = ObsidianSyncEngine(str(vault), vector_store_factory=FakeVectorStore).apply(db, "u1", "p1")

    db.refresh(memory)
    assert memory.content == "new from vault"
    assert memory.qdrant_point_id == "point-topic"
    assert report["summary"]["applied"] == 1
    assert report["applied"][0]["action"] == "update_memory"
    assert FakeVectorStore.calls[0]["text"] == "new from vault"


def test_apply_db_changed_updates_existing_vault_file_in_place(db, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    path = write_note(vault / "topic.md", "topic", "old")
    memory = add_memory(db, "topic", "old", path)
    add_state(db, memory, path)
    db.commit()

    memory.content = "new from db"
    db.commit()

    report = ObsidianSyncEngine(str(vault), vector_store_factory=FakeVectorStore).apply(db, "u1", "p1")

    assert path.exists()
    assert "new from db" in path.read_text(encoding="utf-8")
    assert len(list(vault.rglob("*.md"))) == 1
    assert report["summary"]["applied"] == 1
    assert report["applied"][0]["action"] == "update_vault_file"


def test_apply_conflict_and_deletion_are_non_destructive_by_default(db, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    conflict_path = write_note(vault / "conflict.md", "conflict", "old")
    conflict = add_memory(db, "conflict", "old", conflict_path)
    add_state(db, conflict, conflict_path)

    deleted_path = write_note(vault / "deleted.md", "deleted", "old")
    deleted = add_memory(db, "deleted", "old", deleted_path)
    add_state(db, deleted, deleted_path)
    db.commit()

    conflict.content = "new from db"
    write_note(conflict_path, "conflict", "new from vault")
    deleted_path.unlink()
    db.commit()

    report = ObsidianSyncEngine(str(vault), vector_store_factory=FakeVectorStore).apply(db, "u1", "p1")

    db.refresh(conflict)
    db.refresh(deleted)
    assert conflict.content == "new from db"
    assert "new from vault" in conflict_path.read_text(encoding="utf-8")
    assert deleted.obsidian_path == str(deleted_path.resolve())
    assert deleted.qdrant_point_id == "point-deleted"
    assert report["summary"]["conflicts"] == 1
    assert any(item["state"] == "vault_deleted" for item in report["skipped"])


def test_apply_vault_only_creates_memory_and_db_only_creates_vault_file(db, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_note(vault / "vault_only.md", "vault_only", "from vault")
    db_only = add_memory(db, "db_only", "from db")
    db.commit()

    report = ObsidianSyncEngine(str(vault), vector_store_factory=FakeVectorStore).apply(db, "u1", "p1")

    titles = {memory.title for memory in db.query(Memory).all()}
    assert {"vault_only", "db_only"}.issubset(titles)
    db.refresh(db_only)
    assert db_only.obsidian_path is not None
    assert Path(db_only.obsidian_path).exists()
    assert report["summary"]["applied"] == 2
    assert db.query(ObsidianSyncState).count() == 2
