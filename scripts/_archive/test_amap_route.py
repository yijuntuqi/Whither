"""临时验证：高德 MCP plan_route_between_spots 直连测试（故宫→景山公园，北京）
验证点：MCP 15 工具加载 / 公交+步行路线解析 / 二次调用走缓存"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from dotenv import load_dotenv

load_dotenv()

from backend.app.agent.mcp_amap import load_amap_tools
from backend.app.agent.tools import plan_route_between_spots


async def main():
    n = await load_amap_tools()
    print(f"[1] amap tools loaded: {n}")

    r = await plan_route_between_spots.ainvoke(
        {"origin": "故宫", "destination": "景山公园", "city": "北京"})
    print(f"[2] 首次查询:\n{r}")

    r2 = await plan_route_between_spots.ainvoke(
        {"origin": "故宫", "destination": "景山公园", "city": "北京"})
    print(f"[3] 二次查询（应带 cached 标记）:\n{r2}")


asyncio.run(main())
