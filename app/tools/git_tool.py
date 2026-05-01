from app.tools.shell_tool import run_safe


def status(cwd: str = ".") -> str:
    return run_safe("git status", cwd=cwd)
