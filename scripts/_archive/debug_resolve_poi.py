"""临时调试：直接调 _resolve_poi 打印中间返回，定位 plan_route 内部失败点"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from dotenv import load_dotenv

load_dotenv()

from backend.app.agent.mcp_amap import load_amap_tools, get_amap_tool
from backend.app.agent.tools import _mcp_parse, _resolve_poi


async def main():
    await load_amap_tools()
    t_search = get_amap_tool("maps_text_search")
    t_detail = get_amap_tool("maps_search_detail")

    r = _mcp_parse(await t_search.ainvoke({"keywords": "故宫", "city": "北京"}))
    print("[raw search]", json.dumps(r, ensure_ascii=False)[:300])
    await asyncio.sleep(0.4)

    poi = await _resolve_poi(t_search, t_detail, "故宫", "北京")
    print(f"[resolve_poi 故宫] -> {poi}")
    await asyncio.sleep(0.4)

    poi2 = await _resolve_poi(t_search, t_detail, "景山公园", "北京")
    print(f"[resolve_poi 景山公园] -> {poi2}")


asyncio.run(main())
