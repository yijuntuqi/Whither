# -*- coding: utf-8 -*-
"""
12306 官方接口直连（无第三方 MCP 依赖，数据权威实时）
- 站名代码表：station_name.js（进程内缓存，3388 站）
- 余票：otn/leftTicket/queryG（依次回退 queryZ/queryA/query）
- 票价：otn/leftTicket/queryTicketPrice
注意：12306 预售期约 15 天；超时未售返回 IS_TIME_NOT_BUY。
"""
import asyncio

import httpx
from loguru import logger

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
_INIT_URL = "https://kyfw.12306.cn/otn/leftTicket/init"
_QUERY_EPS = ["queryG", "queryZ", "queryA", "query"]
_PRICE_URL = "https://kyfw.12306.cn/otn/leftTicket/queryTicketPrice"

# 余票字段索引 → 座位等级中文名（58 字段格式，已实测）
_SEAT_FIELDS = {
    21: "高级软卧", 23: "软卧", 24: "软座", 25: "特等座",
    26: "无座", 28: "硬座", 29: "硬卧",
    30: "二等座", 31: "一等座", 32: "商务座", 33: "动卧",
}

# 票价接口座位代码 → 中文名
_PRICE_CODES = {
    "WZ": "无座", "O": "二等座", "M": "一等座", "9": "商务座",
    "SWZ": "商务座", "A9": "高级软卧", "4": "软卧", "AI": "一等卧",
    "AJ": "二等卧", "1": "硬座", "A3": "硬卧", "6": "软座",
}

_station_map: dict[str, str] | None = None


async def _load_station_map(client: httpx.AsyncClient) -> dict[str, str]:
    """加载并缓存 站名→电报码"""
    global _station_map
    if _station_map is not None:
        return _station_map
    r = await client.get(_STATION_URL)
    r.raise_for_status()
    text = r.text
    raw = text.split("='", 1)[-1].rstrip("';")
    m: dict[str, str] = {}
    for chunk in raw.split("@"):
        p = chunk.split("|")
        if len(p) >= 3 and p[1]:
            m[p[1]] = p[2]
    _station_map = m
    logger.info(f"12306 站名表加载成功: {len(m)} 站")
    return m


def _resolve_code(smap: dict[str, str], name: str) -> str | None:
    """城市/站名 → 电报码。支持「武汉」城市级（12306 自动含同城各站）"""
    name = (name or "").strip().removesuffix("站")
    if name in smap:
        return smap[name]
    if (name + "站") in smap:
        return smap[name + "站"]
    return None


def _parse_seats(p: list[str]) -> dict[str, str]:
    """解析余票：空串=无此席别；「有」=可购；「无」=售罄；数字=剩余张数"""
    seats = {}
    for idx, label in _SEAT_FIELDS.items():
        v = p[idx].strip() if idx < len(p) else ""
        if v:
            seats[label] = v
    return seats


async def _fetch_price(client: httpx.AsyncClient, t: dict, date: str) -> dict[str, str]:
    """单车次票价查询，失败返回 {}"""
    try:
        r = await client.get(_PRICE_URL, params={
            "train_no": t["train_no"],
            "from_station_no": t["from_no"],
            "to_station_no": t["to_no"],
            "seat_types": t["seat_types"],
            "train_date": date,
        })
        j = r.json()
        if not j.get("status"):
            return {}
        out: dict[str, str] = {}
        data = j.get("data") or {}
        for code, price in data.items():
            label = _PRICE_CODES.get(code)
            if label and isinstance(price, str) and price.startswith("¥"):
                out[label] = price
        return out
    except Exception:
        return {}


async def query_tickets(origin: str, destination: str, date: str,
                        max_price_rows: int = 6) -> list[dict]:
    """查询跨城火车余票（含票价）。

    返回：[{"code","from","to","dep","arr","duration","can_buy","seats","prices",...}]
    出错或未到起售日抛异常，由工具层转成用户可读文本。
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": _UA}, follow_redirects=True, timeout=20
    ) as client:
        smap = await _load_station_map(client)
        oc = _resolve_code(smap, origin)
        dc = _resolve_code(smap, destination)
        if not oc or not dc:
            raise ValueError(f"无法识别车站/城市：{origin if not oc else destination}")

        await client.get(_INIT_URL)  # 取 JSESSIONID 等 Cookie
        params = {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": oc,
            "leftTicketDTO.to_station": dc,
            "purpose_codes": "ADULT",
        }
        data = None
        for ep in _QUERY_EPS:
            try:
                r = await client.get(
                    f"https://kyfw.12306.cn/otn/leftTicket/{ep}", params=params)
                j = r.json()
                if j.get("status") and isinstance(j.get("data"), dict) \
                        and j["data"].get("result") is not None:
                    data = j["data"]
                    break
            except Exception:
                continue
        if data is None:
            raise RuntimeError("12306 余票接口查询失败（网络或服务波动）")

        code2name = {v: k for k, v in smap.items()}
        trains: list[dict] = []
        for row in data.get("result", []):
            p = row.split("|")
            trains.append({
                "code": p[3],
                "from": code2name.get(p[6], p[6]),
                "to": code2name.get(p[7], p[7]),
                "dep": p[8], "arr": p[9], "duration": p[10],
                "can_buy": p[11], "seats": _parse_seats(p),
                "train_no": p[2], "from_no": p[16], "to_no": p[17],
                "seat_types": p[35],
            })

        if not trains:
            return []

        # 票价：只查可购（Y）的前若干趟，顺序请求避免触发限流
        buyable = [t for t in trains if t["can_buy"] == "Y"][:max_price_rows]
        for i, t in enumerate(buyable):
            t["prices"] = await _fetch_price(client, t, date)
            if i < len(buyable) - 1:
                await asyncio.sleep(0.25)
        return trains
