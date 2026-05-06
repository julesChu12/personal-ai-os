import importlib.util
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import Memory
from app.memory.memory_pipeline import MemoryPipeline
from app.memory.obsidian_importer import ObsidianImporter


IMPORT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_obsidian_vault.py"
SPEC = importlib.util.spec_from_file_location("import_obsidian_vault", IMPORT_SCRIPT)
import_obsidian_vault = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(import_obsidian_vault)


class FakeVectorStore:
    def upsert_memory(self, text, payload, point_id=None):
        return point_id or f"point-{payload['title']}"


class FailingPipeline:
    def persist(self, db, user_id, project_id, session_id, candidates):
        raise RuntimeError("persist failed")


def build_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def build_importer(vault_path):
    pipeline = MemoryPipeline(vector_store_factory=FakeVectorStore)
    return ObsidianImporter(vault_path=str(vault_path), pipeline=pipeline)


def build_temp_vault(tmp_path):
    vault = tmp_path / "my_vault"
    vault.mkdir()

    (vault / "note1.md").write_text("This is note 1 content.", encoding="utf-8")
    (vault / "note2.md").write_text(
        """---
type: concept
tags: [ai, os]
importance: 9
---
This is note 2 content with tags.""",
        encoding="utf-8",
    )
    sub = vault / "Subfolder"
    sub.mkdir()
    (sub / "note3.md").write_text("Note 3 in subfolder.", encoding="utf-8")

    hidden = vault / ".obsidian"
    hidden.mkdir()
    (hidden / "hidden.md").write_text("Should be ignored.", encoding="utf-8")
    return vault


def test_obsidian_importer_basic(tmp_path):
    db = build_db_session()
    vault = build_temp_vault(tmp_path)
    importer = build_importer(vault)

    result = importer.import_vault(db, "user1", "project1")

    assert result.scanned == 3
    assert result.imported == 3
    assert result.created == 3

    memories = db.query(Memory).all()
    assert len(memories) == 3
    titles = [memory.title for memory in memories]
    assert "note1" in titles
    assert "note2" in titles
    assert "note3" in titles

    note2 = db.query(Memory).filter_by(title="note2").first()
    assert note2.memory_type == "concept"
    assert "ai" in note2.tags
    assert "os" in note2.tags
    assert note2.importance == 9
    assert "This is note 2 content with tags." in note2.content
    assert note2.obsidian_path == str((vault / "note2.md").absolute())


def test_obsidian_importer_reports_unchanged_and_updated_files(tmp_path):
    db = build_db_session()
    vault = build_temp_vault(tmp_path)
    importer = build_importer(vault)

    first = importer.import_vault(db, "user1", "project1")
    second = importer.import_vault(db, "user1", "project1")

    assert first.imported == 3
    assert second.imported == 0
    assert second.unchanged == 3
    assert db.query(Memory).count() == 3

    (vault / "note1.md").write_text("Updated content for note 1.", encoding="utf-8")
    third = importer.import_vault(db, "user1", "project1")

    assert third.imported == 1
    assert third.updated == 1
    assert third.unchanged == 2
    note1 = db.query(Memory).filter_by(title="note1").first()
    assert note1.content == "Updated content for note 1."


def test_obsidian_importer_dry_run_reports_without_persisting(tmp_path):
    db = build_db_session()
    vault = tmp_path / "vault"
    note = vault / "Projects" / "personal.md"
    note.parent.mkdir(parents=True)
    note.write_text("stable note\n", encoding="utf-8")
    importer = build_importer(vault)

    result = importer.import_vault(db, "u1", "p1", dry_run=True)

    assert result.to_dict()["dry_run"] is True
    assert result.to_dict()["scanned"] == 1
    assert result.to_dict()["created"] == 1
    assert result.to_dict()["imported"] == 0
    assert db.query(Memory).count() == 0


def test_obsidian_importer_reports_failed_persist(tmp_path):
    db = build_db_session()
    vault = tmp_path / "vault"
    note = vault / "broken.md"
    vault.mkdir()
    note.write_text("broken note\n", encoding="utf-8")
    importer = ObsidianImporter(vault_path=str(vault), pipeline=FailingPipeline())

    result = importer.import_vault(db, "u1", "p1")

    assert result.failed == 1
    assert result.imported == 0
    assert result.items[0]["path"] == "broken.md"
    assert result.items[0]["status"] == "failed"
    assert "persist failed" in result.items[0]["error"]


def test_import_obsidian_vault_formats_operational_summary(tmp_path):
    db = build_db_session()
    vault = tmp_path / "vault"
    note = vault / "note.md"
    vault.mkdir()
    note.write_text("note\n", encoding="utf-8")
    importer = build_importer(vault)

    result = importer.import_vault(db, "u1", "p1", dry_run=True)

    assert import_obsidian_vault.format_result(result) == (
        "obsidian import (dry-run): scanned=1 imported=0 created=1 updated=0 unchanged=0 skipped=0 failed=0"
    )
