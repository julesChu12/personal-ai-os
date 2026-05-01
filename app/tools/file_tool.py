from pathlib import Path


def read_text(path: str, base_dir: str = ".") -> str:
    """读取 base_dir 内的文本文件，拒绝路径逃逸。"""
    safe_path = resolve_within_base(path, base_dir)
    if not safe_path.is_file():
        raise ValueError("path is not a file")
    return safe_path.read_text(encoding="utf-8")


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
