"""临时验证：验收②③ —— 断网降级 + PDF 模板 transit_from_prev 渲染
1) AMAP_MCP_URL 指向不可达地址 → load_amap_tools 返回 0，plan_route 返回降级文案不崩
2) 行程 JSON 带 transit_from_prev → render_html 输出包含灰色交通行"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from dotenv import load_dotenv

load_dotenv()

# ---- 1) 断网降级：覆盖为不可达 URL（必须在导入 mcp_amap 之前设置）----
os.environ["AMAP_MCP_URL"] = "https://127.0.0.1:9/mcp"

from backend.app.agent.mcp_amap import load_amap_tools
from backend.app.agent.tools import plan_route_between_spots


async def offline_test():
    n = await load_amap_tools()
    print(f"[断网] load_amap_tools -> {n} (期望 0，不抛异常)")
    # 未缓存的对：应返回降级文案而非崩溃
    r = await plan_route_between_spots.ainvoke(
        {"origin": "故宫", "destination": "天坛公园", "city": "北京"})
    print(f"[断网] 未缓存对 plan_route -> {r.strip()[:60]}")
    assert "建议现场导航" in r or "暂不可用" in r, "降级文案缺失"
    # 已缓存的对：离线也应命中缓存（缓存优先于可用性检查，属预期行为）
    r2 = await plan_route_between_spots.ainvoke(
        {"origin": "故宫", "destination": "景山公园", "city": "北京"})
    print(f"[断网] 已缓存对 plan_route -> {r2.strip()[:60]}")
    assert "(cached)" in r2, "离线缓存未命中"
    print("[断网] OK：服务不可达时优雅降级，已缓存路线离线可用")


asyncio.run(offline_test())

# ---- 2) 模板渲染 ----
from backend.app.pdf.template import render_html

fake = {
    "title": "北京一日游",
    "city": "北京",
    "days": [{
        "day": 1,
        "title": "经典中轴一日",
        "items": [
            {"time": "09:00", "name": "故宫", "note": "提前7天预约"},
            {"time": "13:00", "name": "景山公园", "note": "万春亭俯瞰紫禁城",
             "transit_from_prev": {"mode": "124路（神武门→景山东门）",
                                   "duration": "37分钟", "distance": "934m", "cost": 2}},
            {"time": "15:30", "name": "南锣鼓巷", "note": "胡同漫步",
             "transit_from_prev": {"mode": "步行", "duration": "18分钟", "distance": "1.5km"}},
        ],
    }],
}
html = render_html(fake)
n_badge = html.count("transit-line")
print(f"[模板] transit-line 出现次数: {n_badge} (期望 2)")
assert "前往本站：124路（神武门→景山东门） · 37分钟 · 934m" in html, "公交徽章内容缺失"
assert "前往本站：步行 · 18分钟 · 1.5km" in html, "步行徽章内容缺失"
print("[模板] OK：景点卡上方灰色交通行渲染正确")
print("\n全部通过 ✅")
