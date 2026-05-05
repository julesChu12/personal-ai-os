from pathlib import Path


def append_note(path: str, content: str, vault_path: str) -> dict[str, int | str]:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    safe_path = _resolve_within_vault(path, vault_path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    text = content.rstrip() + "\n"
    with safe_path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    return {"path": str(Path(path)), "bytes": len(text.encode("utf-8"))}


def _resolve_within_vault(path: str, vault_path: str) -> Path:
    vault = Path(vault_path).resolve()
    candidate_path = Path(path)
    candidate = candidate_path.resolve() if candidate_path.is_absolute() else (vault / candidate_path).resolve()
    try:
        candidate.relative_to(vault)
    except ValueError as exc:
        raise ValueError("path is outside allowed vault") from exc
    return candidate
