from app.memory.obsidian_writer import ObsidianWriter
from app.memory.memory_schema import MemoryCandidate


def test_obsidian_writer(tmp_path):
    writer = ObsidianWriter(str(tmp_path))
    p = writer.write_memory("u", "p", "s", MemoryCandidate(title="测试", content="内容"))
    assert p.endswith(".md")
