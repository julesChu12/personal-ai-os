import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Memory
from app.memory.obsidian_importer import ObsidianImporter
from app.memory.memory_pipeline import MemoryPipeline


engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


class FakeVectorStore:
    def upsert_memory(self, text, payload, point_id=None):
        return point_id or f"point-{payload['title']}"


def build_importer(vault_path):
    pipeline = MemoryPipeline(vector_store_factory=FakeVectorStore)
    return ObsidianImporter(vault_path=str(vault_path), pipeline=pipeline)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "my_vault"
    vault.mkdir()
    
    # 文件 1: 简单文件
    (vault / "note1.md").write_text("This is note 1 content.", encoding="utf-8")
    
    # 文件 2: 带 Frontmatter
    (vault / "note2.md").write_text("""---
type: concept
tags: [ai, os]
importance: 9
---
This is note 2 content with tags.""", encoding="utf-8")
    
    # 文件 3: 子目录下的文件
    sub = vault / "Subfolder"
    sub.mkdir()
    (sub / "note3.md").write_text("Note 3 in subfolder.", encoding="utf-8")
    
    # 文件 4: 隐藏目录（应忽略）
    hidden = vault / ".obsidian"
    hidden.mkdir()
    (hidden / "hidden.md").write_text("Should be ignored.", encoding="utf-8")
    
    return vault

def test_obsidian_importer_basic(db, temp_vault):
    # 模拟环境变量中的 vault 路径
    importer = build_importer(temp_vault)
    
    count = importer.import_vault(db, "user1", "project1")
    
    # 应导入 3 个文件（note1, note2, note3）
    assert count == 3
    
    # 验证数据库记录
    memories = db.query(Memory).all()
    assert len(memories) == 3
    
    titles = [m.title for m in memories]
    assert "note1" in titles
    assert "note2" in titles
    assert "note3" in titles
    
    # 验证 frontmatter 解析
    note2 = db.query(Memory).filter_by(title="note2").first()
    assert note2.memory_type == "concept"
    assert "ai" in note2.tags
    assert "os" in note2.tags
    assert note2.importance == 9
    assert "This is note 2 content with tags." in note2.content
    
    # 验证路径保留（没有生成带时间戳的新文件）
    assert note2.obsidian_path == str((temp_vault / "note2.md").absolute())

def test_obsidian_importer_idempotency(db, temp_vault):
    importer = build_importer(temp_vault)
    
    # 第一次导入
    count1 = importer.import_vault(db, "user1", "project1")
    assert count1 == 3
    
    # 第二次导入（无变化）
    count2 = importer.import_vault(db, "user1", "project1")
    # MemoryPipeline.persist 会返回所有保存（包括跳过的）
    # 但由于我们在 persist 逻辑中对完全重复的记忆使用了 continue 且 saved.append(existing)
    # 所以返回的数量应该还是一样，但 commit 次数应为 0
    assert count2 == 3
    
    # 修改一个文件内容
    (temp_vault / "note1.md").write_text("Updated content for note 1.", encoding="utf-8")
    count3 = importer.import_vault(db, "user1", "project1")
    assert count3 == 3
    
    note1 = db.query(Memory).filter_by(title="note1").first()
    assert note1.content == "Updated content for note 1."
