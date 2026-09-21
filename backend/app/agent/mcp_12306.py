"""
12306 MCP Server 接入（stdio）
- 通过 npx 启动 12306-mcp，提供余票/票价/中转查询等工具
- 启动失败（无网络/npm 源慢等）时优雅降级，返回空列表
"""
import sys

from loguru import logger


async def get_12306_tools() -> list:
    """返回 12306 MCP 工具列表；失败返回 []"""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        client = MultiServerMCPClient({
            "12306": {
                "command": "npx",
                "args": ["-y", "12306-mcp"],
                "transport": "stdio",
            }
        })
        tools = await client.get_tools()
        logger.info(f"12306 MCP 加载成功: {[t.name for t in tools]}")
        return tools
    except Exception as e:
        logger.warning(f"12306 MCP 不可用（余票查询将降级为建议用户自行查询）: {type(e).__name__}: {e}")
        return []
