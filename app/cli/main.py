import typer
import httpx

app = typer.Typer()
API = "http://localhost:8000"


@app.command()
def chat(message: str, project: str = "personal-ai-os", session: str = "default", user: str = "jules"):
    payload = {"user_id": user, "project_id": project, "session_id": session, "message": message, "mode": "chat"}
    r = httpx.post(f"{API}/chat", json=payload, timeout=120)
    typer.echo(r.json())


@app.command("memory-search")
def memory_search(query: str, project: str = "personal-ai-os", user: str = "jules"):
    r = httpx.get(f"{API}/memory/search", params={"user_id": user, "project_id": project, "query": query})
    typer.echo(r.json())


if __name__ == "__main__":
    app()
