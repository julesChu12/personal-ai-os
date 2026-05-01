import subprocess
import shlex

ALLOWED = {("pwd",), ("ls",), ("git", "status")}


def run_safe(command: str, cwd: str = ".") -> str:
    args = tuple(shlex.split(command))
    if args not in ALLOWED:
        raise ValueError(f"Command not allowed: {command}")
    result = subprocess.run(args, cwd=cwd, shell=False, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr
