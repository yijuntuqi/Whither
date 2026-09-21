"""
高德地图 MCP Server 接入（Streamable HTTP）
- 官方 MCP: https://mcp.amap.com/mcp?key=KEY（15 个工具：geo/公交/步行/驾车/距离等）
- 不把 15 个原始工具塞给 Agent（20+ 工具易选错、费 token），
  仅由 tools.plan_route_between_spots 在内部调用，失败优雅降级
"""
import os

from loguru import logger

# 模块级缓存：name -> await tool.ainvoke(args) 可调用
_amap_tools: dict = {}


def get_amap_tool(name: str):
    """返回指定高德 MCP 工具（未加载/加载失败返回 None，调用方自行降级）"""
    return _amap_tools.get(name)


async def load_amap_tools() -> int:
    """连接高德 MCP 并缓存全部工具；失败返回 0（Agent 不带交通查询继续工作）"""
    if _amap_tools:  # 已加载
        return len(_amap_tools)
    url = os.getenv("AMAP_MCP_URL")
    if not url:
        logger.warning("AMAP_MCP_URL 未配置，景点间交通查询将降级为『建议现场导航』")
        return 0
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        try:
            transport = "streamable_http"
            client = MultiServerMCPClient({"amap": {"transport": transport, "url": url}})
            tools = await client.get_tools()
        except Exception:
            # streamable_http 报错时退回 http 传输
            transport = "http"
            client = MultiServerMCPClient({"amap": {"transport": transport, "url": url}})
            tools = await client.get_tools()
        for t in tools:
            _amap_tools[t.name] = t
        logger.info(f"高德 MCP 加载成功（{transport}）: {[t.name for t in tools]}")
        return len(_amap_tools)
    except Exception as e:
        logger.warning(f"高德 MCP 不可用（交通查询降级，不影响其他功能）: {type(e).__name__}: {e}")
        _amap_tools.clear()
        return 0
