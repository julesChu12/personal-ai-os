from typing import AsyncIterator

from app.core.model_router import ModelRouter
from app.memory.retriever import Retriever


class Orchestrator:
    """聊天编排入口，负责把长期记忆检索结果注入模型上下文。"""

    def __init__(self) -> None:
        self.model = ModelRouter()
        self.retriever = Retriever()

    def chat(self, user_id: str, project_id: str, session_id: str, message: str) -> dict:
        """执行一次非流式聊天，并返回回答、使用的记忆和基础 trace。"""
        memories = self.retriever.search(user_id, project_id, message, top_k=5)
        memory_text = "\n".join([str(m.get("payload", {})) for m in memories])

        messages = [
            {"role": "system", "content": "你是用户的 Personal AI OS。你需要帮助用户学习、编程、创业、研究，并持续沉淀长期记忆。\n注意：当前处于纯文本对话模式，你没有直接访问互联网、执行系统命令或使用 bash 工具的能力。绝对不要输出 [TOOL_CALL] 这样的标记。如果用户让你总结 URL，请明确告知用户你无法直接联网，并请他们将内容复制给你。"},
            {"role": "system", "content": f"可用长期记忆：\n{memory_text}"},
            {"role": "user", "content": message},
        ]
        answer = self.model.chat(messages)
        return {
            "answer": answer,
            "memory_used": memories,
            "agent_trace": [{"agent": "orchestrator", "action": "chat"}],
        }

    async def chat_stream(
        self,
        user_id: str,
        project_id: str,
        session_id: str,
        message: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """执行一次 OpenAI-compatible SSE 流式聊天。"""
        memories = self.retriever.search(user_id, project_id, message, top_k=5)
        memory_text = "\n".join([str(m.get("payload", {})) for m in memories])

        messages = [
            {"role": "system", "content": "你是用户的 Personal AI OS。你需要帮助用户学习、编程、创业、研究，并持续沉淀长期记忆。\n注意：当前处于纯文本对话模式，你没有直接访问互联网、执行系统命令或使用 bash 工具的能力。绝对不要输出 [TOOL_CALL] 这样的标记。如果用户让你总结 URL，请明确告知用户你无法直接联网，并请他们将内容复制给你。"},
            {"role": "system", "content": f"可用长期记忆：\n{memory_text}"},
            {"role": "user", "content": message},
        ]
        async for chunk in self.model.chat_stream(messages, model=model):
            yield chunk

    def task(self, user_id: str, project_id: str, session_id: str, task: str, agents: list[str]) -> dict:
        """临时任务入口；真实多 Agent 编排落地前复用聊天链路。"""
        prompt = f"请作为多 Agent 系统规划并完成任务：{task}\n指定 agents: {agents}"
        return self.chat(user_id, project_id, session_id, prompt)
