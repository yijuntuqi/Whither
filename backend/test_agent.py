"""M1 核心链路测试：本地工具单测 + 12306 MCP + Agent e2e"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()


async def main():
    print("=== 1. 本地工具单测 ===")
    from backend.app.agent.tools import calculate_budget, generate_packing_list, search_travel_knowledge

    out = calculate_budget.invoke({"items": [
        {"category": "交通", "name": "高铁往返", "amount": 120, "qty": 2},
        {"category": "餐饮", "name": "正餐", "amount": 60, "qty": 3},
        {"category": "门票", "name": "瓷房子", "amount": 50, "qty": 1},
    ]})
    print(out)
    print()

    out = generate_packing_list.invoke({"destination": "哈尔滨", "days": 3,
                                        "season": "冬", "weather": "零下20度有雪",
                                        "activities": "滑雪 拍照"})
    print(out[:200], "...")
    print()

    out = search_travel_knowledge.invoke({"query": "一日游怎么玩", "city": "天津"})
    print(out[:300], "...")

    print("\n=== 2. Tavily 实时搜索 ===")
    from backend.app.agent.tools import search_web_info
    out = search_web_info.invoke({"query": "北京 明天 天气"})
    print(out[:200], "...")

    print("\n=== 3. 12306 MCP 加载 ===")
    from backend.app.agent.mcp_12306 import get_12306_tools
    mcp_tools = await get_12306_tools()
    print(f"12306 工具: {[t.name for t in mcp_tools] or '(不可用，已降级)'}")

    print("\n=== 4. Agent e2e（北京→天津 一日游） ===")
    from backend.app.agent.graph import build_agent
    agent = await build_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content":
         "本周六北京到天津一日游，高铁往返，帮我看看有什么好玩的、查下天气和车票，最后给我行程和预算"}]},
        {"configurable": {"thread_id": "m1-test"}},
    )
    for msg in result["messages"]:
        if msg.type == "ai" and msg.tool_calls:
            for tc in msg.tool_calls:
                args = ", ".join(f"{k}={str(v)[:50]!r}" for k, v in tc["args"].items())
                print(f"  🔧 {tc['name']}({args})")
    print(f"\n最终回答（前 1200 字）:\n{result['messages'][-1].content[:1200]}")


if __name__ == "__main__":
    asyncio.run(main())
