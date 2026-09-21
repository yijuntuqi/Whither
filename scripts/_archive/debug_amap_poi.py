"""临时调试：查看 maps_text_search / maps_search_detail 原始返回，排查定位失败"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from dotenv import load_dotenv

load_dotenv()

from backend.app.agent.mcp_amap import load_amap_tools, get_amap_tool
from backend.app.agent.tools import _mcp_parse


async def main():
    await load_amap_tools()
    t_search = get_amap_tool("maps_text_search")
    t_detail = get_amap_tool("maps_search_detail")

    r1 = _mcp_parse(await t_search.ainvoke({"keywords": "故宫", "city": "北京"}))
    print("[text_search 故宫] ")
    print(json.dumps(r1, ensure_ascii=False)[:800])
    await asyncio.sleep(1.5)

    pois = r1.get("pois", []) if isinstance(r1, dict) else []
    print(f"pois: {len(pois)}, first keys: {list(pois[0].keys()) if pois else 'N/A'}")
    if pois and not pois[0].get("location"):
        r2 = _mcp_parse(await t_detail.ainvoke({"id": pois[0]["id"]}))
        print("[search_detail]")
        print(json.dumps(r2, ensure_ascii=False)[:800])


asyncio.run(main())
