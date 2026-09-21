"""M3.5 e2e：对话式规划 → agent 调 export_itinerary_pdf → 落地 PDF"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from backend.app.agent.graph import build_agent
    agent = await build_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content":
         "帮我规划本周六北京→天津一日游：高铁往返、逛景点吃午饭，天气和车票都查一下，"
         "完成后直接导出PDF手册"}]},
        {"configurable": {"thread_id": "pdf-e2e"}, "recursion_limit": 80},
    )
    for msg in result["messages"]:
        if msg.type == "ai" and msg.tool_calls:
            for tc in msg.tool_calls:
                args_preview = {k: (str(v)[:60] + "...") if len(str(v)) > 60 else v for k, v in tc["args"].items()}
                print(f"🔧 {tc['name']}({args_preview})")
    print(f"\n最终回答:\n{result['messages'][-1].content[:600]}")


if __name__ == "__main__":
    asyncio.run(main())
