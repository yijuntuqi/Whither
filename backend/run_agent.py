"""
Whither Agent CLI 交互入口（M1：RAG + 天气 + 12306 + 预算 + 打包清单）
用法:
  E:\\conda_envs\\langchain\\python.exe backend/run_agent.py            # chatanywhere LLM
  E:\\conda_envs\\langchain\\python.exe backend/run_agent.py --local    # 本地 Ollama qwen2.5:7b
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()


async def main():
    if "--local" in sys.argv:
        os.environ["LLM_PROVIDER"] = "ollama"

    from backend.app.agent.graph import build_agent
    agent = await build_agent()
    thread_id = uuid.uuid4().hex[:8]
    config = {"configurable": {"thread_id": thread_id}}

    model = agent.nodes["model"].bound if "model" in agent.nodes else None
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "?")
    provider = "Ollama(本地)" if "--local" in sys.argv else f"OpenAI({os.getenv('OPENAI_API_BASE', '')})"

    print("=" * 56)
    print("🧭 Whither 旅行规划助手（输入 q 退出）")
    print(f"   会话ID: {thread_id}")
    print(f"   模型: {model_name}  [{provider}]")
    print("=" * 56)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in {"q", "quit", "exit"}:
            break

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]},
            {"configurable": {"thread_id": thread_id}, "recursion_limit": 80},
        )

        # 打印工具调用轨迹 + 最终回答
        for msg in result["messages"]:
            if msg.type == "ai" and msg.tool_calls:
                for tc in msg.tool_calls:
                    args = ", ".join(f"{k}={str(v)[:40]!r}" for k, v in tc["args"].items())
                    print(f"  🔧 调用工具: {tc['name']}({args})")

        print(f"\nWhither: {result['messages'][-1].content}")

    print("\n再见！")


if __name__ == "__main__":
    asyncio.run(main())
