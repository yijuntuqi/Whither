"""三隐患修复验证：持久化记忆（跨进程）+ 矩阵缓存检索 + PDF 浏览器降级"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

MODE = sys.argv[1] if len(sys.argv) > 1 else "phase1"
THREAD = "persist-verify-001"


async def phase1():
    """进程1：写入记忆 + 测矩阵缓存 + PDF 降级"""
    print("--- 进程1 ---")

    # 修复2：矩阵缓存
    import time
    from backend.app.rag.retriever import get_retriever
    r = get_retriever()
    t0 = time.time(); res = r.search("成都美食", city="成都", top_k=2); t1 = time.time()
    print(f"① 首查（含建缓存）{t1-t0:.2f}s -> {len(res)}条")
    t0 = time.time(); res = r.search("成都火锅", city="成都", top_k=2); t1 = time.time()
    print(f"① 复查（纯内存）{t1-t0:.2f}s -> {len(res)}条 [{res[0]['city']}|{res[0]['title'][:20]}]")

    # 修复3：PDF 浏览器降级（conda env 无自带 Chromium，应落到系统 Edge）
    # 注意：同步 Playwright 不能在事件循环内直接调用，用 to_thread 模拟 agent 工具的线程池执行
    from backend.app.pdf.generator import generate_pdf
    pdf = await asyncio.to_thread(generate_pdf, {"title": "修复验证", "origin": "A", "destination": "B",
                        "days": [{"day": 1, "date": "2026-09-20", "items": [
                            {"time": "09:00", "type": "景点", "name": "测试", "duration": "1h", "cost": 0}]}],
                        "references": []})
    print(f"③ PDF 生成 OK: {pdf.name}")

    # 修复1：写入跨进程记忆
    from backend.app.agent.graph import build_agent
    agent = await build_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "请记住我们的暗号：菠萝披萨。简短回复即可"}]},
        {"configurable": {"thread_id": THREAD}, "recursion_limit": 30},
    )
    print(f"② 记忆已写入 thread={THREAD}: {result['messages'][-1].content[:80]}")


async def phase2():
    """进程2（模拟重启）：同一 thread 继续对话，应记得暗号"""
    print("--- 进程2（模拟重启后新进程） ---")
    from backend.app.agent.graph import build_agent
    agent = await build_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "我们的暗号是什么？只回答暗号内容"}]},
        {"configurable": {"thread_id": THREAD}, "recursion_limit": 30},
    )
    answer = result["messages"][-1].content
    print(f"② 新进程回答: {answer[:100]}")
    print(f"② 持久化验证: {'✅ 通过' if '菠萝' in answer else '❌ 失败'}")


if __name__ == "__main__":
    asyncio.run(phase1() if MODE == "phase1" else phase2())
