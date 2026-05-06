import os
import sys
import json
import typer
import httpx
from typing import Optional

app = typer.Typer(help="Personal AI OS CLI - 开发者级交互入口")
agents_app = typer.Typer(help="Agent 运行与记录管理")
app.add_typer(agents_app, name="agents")

API = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("OPENAI_COMPAT_API_KEY", "EMPTY")


def call_api(method: str, path: str, params: Optional[dict] = None, json_data: Optional[dict] = None, use_json: bool = False):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        with httpx.Client(timeout=300) as client:
            if method.upper() == "GET":
                r = client.get(f"{API}{path}", params=params, headers=headers)
            else:
                r = client.post(f"{API}{path}", json=json_data, params=params, headers=headers)
            
            if r.status_code >= 400:
                if use_json:
                    typer.echo(json.dumps(r.json(), ensure_ascii=False))
                else:
                    typer.secho(f"Error ({r.status_code}): {r.text}", fg=typer.colors.RED, err=True)
                sys.exit(1)
            
            res = r.json()
            if use_json:
                typer.echo(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                return res
    except httpx.RequestError as exc:
        typer.secho(f"Network Error: {exc}", fg=typer.colors.RED, err=True)
        sys.exit(1)


@app.command()
def chat(
    message: str, 
    project: str = "personal-ai-os", 
    session: str = "default", 
    user: str = "jules",
    json_output: bool = typer.Option(False, "--json", help="输出原始 JSON 响应")
):
    """发起一次基础对话"""
    payload = {"user_id": user, "project_id": project, "session_id": session, "message": message, "mode": "chat"}
    res = call_api("POST", "/chat", json_data=payload, use_json=json_output)
    if not json_output:
        typer.echo(f"AI: {res.get('message', '')}")


@app.command("memory-search")
def memory_search(
    query: str, 
    project: str = "personal-ai-os", 
    user: str = "jules",
    json_output: bool = typer.Option(False, "--json", help="输出原始 JSON 响应")
):
    """检索长期记忆"""
    res = call_api("GET", "/memory/search", params={"user_id": user, "project_id": project, "query": query}, use_json=json_output)
    if not json_output:
        results = res.get("results", [])
        if not results:
            typer.echo("未找到相关记忆。")
        for i, r in enumerate(results):
            typer.echo(f"[{i+1}] (Score: {r['score']:.2f}) {r['payload'].get('title', '无标题')}")
            typer.echo(f"    {r['payload'].get('content', '')[:100]}...")


@app.command("obsidian-import")
def obsidian_import(
    project: str = "personal-ai-os", 
    user: str = "jules",
    json_output: bool = typer.Option(False, "--json", help="输出原始 JSON 响应")
):
    """导入 Obsidian Vault 到系统记忆库"""
    res = call_api("POST", "/memory/obsidian/import", params={"user_id": user, "project_id": project}, use_json=json_output)
    if not json_output:
        typer.secho(f"导入完成！新增/更新数量: {res.get('imported', 0)}", fg=typer.colors.GREEN)


@agents_app.command("run")
def agents_run(
    task: str,
    project: str = "personal-ai-os",
    session: str = "agent-session",
    user: str = "jules",
    planner_mode: str = "model",
    memory: bool = typer.Option(True, help="是否将结果存入长期记忆"),
    json_output: bool = typer.Option(False, "--json", help="输出原始 JSON 响应")
):
    """运行 Agent 任务"""
    agents = ["memory_agent"] if memory else []
    payload = {
        "user_id": user,
        "project_id": project,
        "session_id": session,
        "task": task,
        "agents": agents,
        "planner_mode": planner_mode
    }
    res = call_api("POST", "/agents/run", json_data=payload, use_json=json_output)
    if not json_output:
        typer.echo(f"Status: {res.get('status', 'unknown')}")
        typer.echo(f"Run ID: {res.get('agent_run_id', 'N/A')}")
        typer.echo("-" * 20)
        typer.echo(f"Answer: {res.get('answer', '无回复')}")
        if res.get("memory_saved"):
            typer.secho(f"(记忆已保存: {res.get('memory_saved')})", fg=typer.colors.CYAN)


@agents_app.command("list-runs")
def agents_list_runs(
    project: str = "personal-ai-os",
    user: str = "jules",
    limit: int = 10,
    json_output: bool = typer.Option(False, "--json", help="输出原始 JSON 响应")
):
    """列出 Agent 运行历史记录"""
    res = call_api("GET", "/agents/runs", params={"user_id": user, "project_id": project, "limit": limit}, use_json=json_output)
    if not json_output:
        runs = res.get("runs", [])
        if not runs:
            typer.echo("无运行记录。")
        for r in runs:
            status_color = typer.colors.GREEN if r["status"] == "ok" else typer.colors.RED
            typer.echo(f"ID: {r['id']} | Status: ", nl=False)
            typer.secho(f"{r['status']}", fg=status_color, nl=False)
            typer.echo(f" | Task: {r['task'][:50]}...")


if __name__ == "__main__":
    app()
