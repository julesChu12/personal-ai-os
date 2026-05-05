from pathlib import Path


def read_text(path: str, base_dir: str = ".") -> str:
    """读取 base_dir 内的文本文件，拒绝路径逃逸。"""
    safe_path = resolve_within_base(path, base_dir)
    if not safe_path.is_file():
        raise ValueError("path is not a file")
    return safe_path.read_text(encoding="utf-8")


def write_text(path: str, content: str, base_dir: str = ".") -> dict[str, int | str]:
    """在 base_dir 内写入新的 UTF-8 文本文件，拒绝路径逃逸和覆盖。"""
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    safe_path = resolve_within_base(path, base_dir)
    if safe_path.exists():
        raise ValueError("path already exists")
    if not safe_path.parent.is_dir():
        raise ValueError("parent directory is not a directory")
    safe_path.write_text(content, encoding="utf-8")
    return {"path": path, "bytes": len(content.encode("utf-8"))}


def resolve_within_base(path: str, base_dir: str = ".") -> Path:
    """解析路径并确保目标仍位于允许的 base_dir 内。"""
    base = Path(base_dir).resolve()
    candidate_path = Path(path)
    candidate = candidate_path.resolve() if candidate_path.is_absolute() else (base / candidate_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("path is outside allowed base") from exc
    return candidate
