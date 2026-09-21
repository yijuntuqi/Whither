"""Agent 工具集：RAG 检索 + 实时搜索 + 预算 + 打包清单"""
import json

from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

from backend.app.rag.retriever import get_retriever


# ============ RAG 知识库 ============

@tool
def search_travel_knowledge(query: str, city: str = "") -> str:
    """检索马蜂窝自由行攻略知识库，返回最相关的攻略片段（含标题、链接、内容摘要）。

    Args:
        query: 检索问题，如"冬天看雪去哪"、"有什么美食推荐"
        city: 城市名。用户提到具体城市时必须传入（如"成都"），检索将只在该城市的攻略内进行；
              用户没有提到城市时留空，进行全库检索。
    """
    retriever = get_retriever()
    results = retriever.search(query, city=city or None, top_k=5)
    header = f"检索范围: {city}" if city else "检索范围: 全库（107 城）"
    return f"{header}\n\n{retriever.format_results(results)}"


@tool
def list_supported_cities() -> str:
    """列出知识库当前覆盖的所有城市（来自马蜂窝自由行攻略）。用于判断某个城市是否有本地知识库数据。"""
    cities = get_retriever().supported_cities()
    return f"知识库覆盖 {len(cities)} 个城市：\n" + "、".join(cities)


# ============ 实时信息（Tavily） ============

@tool
def search_web_info(query: str) -> str:
    """联网搜索实时信息：天气预报、景区开放/闭馆时间、节假日限流、票务政策、当地最新活动等。
    知识库攻略是静态爬取的，涉及"现在/当天/最近"的时效性信息时必须用本工具。

    Args:
        query: 搜索词，如"天津 2026年10月1日 天气预报"、"故宫 周一 闭馆吗"
    """
    from langchain_tavily import TavilySearch
    searcher = TavilySearch(max_results=4)
    raw = searcher.invoke({"query": query})
    parts = []
    for r in raw.get("results", []):
        parts.append(f"【{r.get('title', '')}】\n{r.get('content', '')[:400]}\n来源: {r.get('url', '')}")
    return "\n\n".join(parts) if parts else "没有搜到相关信息。"


# ============ 预算核算 ============

CATEGORY_ORDER = ["交通", "住宿", "餐饮", "门票", "其他"]


@tool
def calculate_budget(items: list[dict]) -> str:
    """核算旅行预算，返回总额与分类占比。做行程规划涉及花费时调用。

    Args:
        items: 花费明细列表，每项 {"category": "交通|住宿|餐饮|门票|其他", "name": "高铁票", "amount": 123, "qty": 2}
               amount 为单价，qty 为数量/人数/次数（默认1）
    """
    totals: dict[str, float] = {}
    details = []
    for it in items:
        cat = it.get("category", "其他")
        if cat not in CATEGORY_ORDER:
            cat = "其他"
        amount = float(it.get("amount", 0)) * float(it.get("qty", 1) or 1)
        totals[cat] = totals.get(cat, 0) + amount
        details.append(f"{cat} | {it.get('name', '')} | {it.get('amount')}×{it.get('qty', 1)} = {amount:.0f}元")

    grand = sum(totals.values())
    lines = [f"{'分类':<4}{'金额':>10}{'占比':>8}", "-" * 26]
    for cat in CATEGORY_ORDER:
        if cat in totals:
            pct = totals[cat] / grand * 100 if grand else 0
            lines.append(f"{cat:<4}{totals[cat]:>9.0f}元{pct:>7.1f}%")
    lines.append("-" * 26)
    lines.append(f"总计 {grand:.0f} 元")

    # 给 PDF 图表用的 JSON
    chart = {"total": round(grand, 2),
             "by_category": {c: round(totals[c], 2) for c in CATEGORY_ORDER if c in totals}}
    return "\n".join(details) + "\n\n" + "\n".join(lines) + f"\n\nbudget_json: {json.dumps(chart, ensure_ascii=False)}"


# ============ 打包清单 ============

def _packing_rules(days: int, season: str, weather: str, activities: str) -> list[str]:
    base = ["身份证/护照", "手机+充电器", "充电宝", "少量现金+银行卡"]
    n = max(1, days)
    items = [f"换洗衣物 ×{min(n + 1, 7)}套", "洗漱包(牙刷/洗发水/护肤品)", "常用药品(肠胃药/感冒药/创可贴)"]

    w = weather + season
    if any(k in w for k in ["雪", "冬", "零下", "冷", "-"]):
        items += ["羽绒服/厚外套", "保暖内衣", "帽子围巾手套", "防滑雪地靴"]
    if any(k in w for k in ["雨", "阵雨", "雷"]):
        items += ["折叠伞/雨衣", "防水鞋", "手机防水袋"]
    if any(k in w for k in ["夏", "高温", "热", "晒"]):
        items += ["防晒霜(SPF50)", "遮阳帽/太阳镜", "便携小风扇", "藿香正气水"]
    if any(k in activities for k in ["徒步", "登山", "爬山", "滑雪"]):
        items += ["运动鞋", "速干衣", "登山杖/护膝"]
    if any(k in activities for k in ["海", "海边", "温泉", "游泳", "潜水"]):
        items += ["泳衣泳镜", "速干浴巾", "拖鞋"]
    if any(k in activities for k in ["拍照", "摄影"]):
        items += ["相机+备用存储卡", "三脚架/自拍杆"]
    if days >= 3:
        items += ["便携洗衣液", "零食"]
    return base + items


@tool
def generate_packing_list(destination: str, days: int, season: str = "", weather: str = "", activities: str = "") -> str:
    """根据目的地、天数、季节天气、活动类型生成打包清单。

    返回 JSON 数组字符串，请将数组内容原样填入 itinerary JSON 的 packing 字段（保持数组类型，不要转成字符串）。

    Args:
        destination: 目的地，如"哈尔滨"
        days: 天数
        season: 季节（春/夏/秋/冬），未知可留空
        weather: 天气描述，如"零下20度有雪"、"有雨"，来自天气查询结果
        activities: 计划活动，如"徒步 滑雪 拍照"
    """
    items = _packing_rules(days, season, weather, activities)
    return json.dumps(items, ensure_ascii=False)


# ============ PDF 行程手册 ============

@tool
def export_itinerary_pdf(itinerary_json: str) -> str:
    """把行程导出为杂志级 PDF 手册（A4，含逐日时间线、预算饼图、打包清单）。

    Args:
        itinerary_json: 完整的行程 JSON 字符串，即你按行程结构化约定输出的 ```itinerary 代码块内容。
                        建议包含 packing 打包清单和 references 攻略引用字段。
    """
    import json as _json
    from backend.app.pdf.generator import generate_pdf

    # 容错：剥掉 LLM 可能带上的 markdown 围栏
    s = itinerary_json.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
        if s.startswith("itinerary"):
            s = s[len("itinerary"):]
        s = s.strip()

    try:
        data = _json.loads(s)
    except _json.JSONDecodeError as e:
        return f"itinerary JSON 解析失败: {e}。请传完整的 JSON 字符串（不要带 ``` 围栏）。"
    pdf_path = generate_pdf(data)
    return f"✅ PDF 手册已生成: {pdf_path}"


# ============ 景点间交通（高德 MCP 封装） ============

import asyncio as _asyncio
import sqlite3 as _sqlite3
from pathlib import Path as _Path

_AMAP_CACHE_DB = _Path(__file__).resolve().parents[2] / "data" / "amap_cache.sqlite"


def _amap_cache_get(key: str) -> str | None:
    try:
        with _sqlite3.connect(_AMAP_CACHE_DB) as conn:
            row = conn.execute(
                "SELECT payload FROM route_cache WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def _amap_cache_put(key: str, payload: str):
    try:
        with _sqlite3.connect(_AMAP_CACHE_DB) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS route_cache "
                "(key TEXT PRIMARY KEY, payload TEXT, created_at TEXT DEFAULT (datetime('now')))")
            conn.execute(
                "INSERT OR REPLACE INTO route_cache(key, payload) VALUES (?, ?)", (key, payload))
            conn.commit()
    except Exception:
        pass


def _mcp_parse(res):
    """MCP 返回 [{type:'text', text:json}] → dict/list；已是原文则原样返回"""
    if isinstance(res, list) and res and isinstance(res[0], dict) and "text" in res[0]:
        import json as _j
        try:
            return _j.loads(res[0]["text"])
        except Exception:
            return res[0]["text"]
    return res


def _fmt_minutes(seconds) -> str:
    try:
        m = int(round(float(seconds) / 60))
        return f"{m}分钟" if m < 60 else f"{m // 60}小时{m % 60:02d}分"
    except (TypeError, ValueError):
        return ""


def _fmt_km(meters) -> str:
    try:
        m = float(meters)
        return f"{m / 1000:.1f}km" if m >= 1000 else f"{m:.0f}m"
    except (TypeError, ValueError):
        return ""


async def _resolve_poi(tool_search, tool_detail, keyword: str, city: str) -> dict | None:
    """关键词 → POI（名称+坐标）。text_search 精简版无坐标，需 search_detail 补全。"""
    r = _mcp_parse(await tool_search.ainvoke({"keywords": keyword, "city": city or "全国"}))
    if not isinstance(r, dict) or not r.get("pois"):
        return None
    poi = r["pois"][0]
    if poi.get("location"):
        return {"name": poi.get("name", keyword), "location": poi["location"]}
    # 个人 Key QPS=3：search→detail 背靠背会被限流返回空结果，必须留间隔
    await _asyncio.sleep(0.4)
    d = _mcp_parse(await tool_detail.ainvoke({"id": poi["id"]}))
    if isinstance(d, dict):
        # 兼容两种返回结构：扁平 {"id","location",...} 或 {"pois":[...]}
        p = d if d.get("location") else (d.get("pois") or [{}])[0]
        if p.get("location"):
            return {"name": p.get("name", poi.get("name", keyword)), "location": p["location"]}
    return None


@tool
async def plan_route_between_spots(origin: str, destination: str, city: str = "") -> str:
    """查询两个景点/地点之间的真实交通方式、时长与距离（高德数据：公交地铁+步行）。

    排完当日景点后，对每对相邻景点调用本工具，把返回的 transit_from_prev 填入行程 JSON。

    Args:
        origin: 出发景点名，如"故宫"
        destination: 到达景点名，如"景山公园"
        city: 所在城市，如"北京"（推荐传入，提高定位精度）
    """
    from backend.app.agent.mcp_amap import get_amap_tool

    cache_key = f"{origin}|{destination}|{city}"
    cached = _amap_cache_get(cache_key)
    if cached:
        return cached + "\n(cached)"

    t_search, t_detail = get_amap_tool("maps_text_search"), get_amap_tool("maps_search_detail")
    t_transit = get_amap_tool("maps_direction_transit_integrated")
    t_walk = get_amap_tool("maps_direction_walking")
    if not (t_search and t_detail and t_transit):
        return f"交通查询服务暂不可用，{origin}→{destination} 建议现场导航或使用地图 App。"

    try:
        po = await _resolve_poi(t_search, t_detail, origin, city)
        await _asyncio.sleep(0.4)
        pd = await _resolve_poi(t_search, t_detail, destination, city)
        await _asyncio.sleep(0.4)
        if not po or not pd:
            return f"未能定位 {origin if not po else destination}，{origin}→{destination} 建议现场导航。"

        o, d = po["location"], pd["location"]
        mode, dur, dist, walk_desc = "", "", "", ""

        r = _mcp_parse(await t_transit.ainvoke(
            {"origin": o, "destination": d, "city": city or "北京", "cityd": city or ""}))
        await _asyncio.sleep(0.4)
        if isinstance(r, dict) and r.get("transits"):
            tr = r["transits"][0]
            dur, dist = _fmt_minutes(tr.get("duration")), _fmt_km(r.get("distance", tr.get("walking_distance", "")))
            bus_segs = []
            for seg in tr.get("segments", []):
                bus = seg.get("bus") or {}
                lines = bus.get("buslines") or []
                if lines:
                    bl = lines[0]
                    seg_name = bl.get("name", "")
                    dep = (bl.get("departure_stop") or {}).get("name", "")
                    arr = (bl.get("arrival_stop") or {}).get("name", "")
                    via = f"（{dep}→{arr}）" if dep and arr else ""
                    bus_segs.append(f"{seg_name}{via}")
            if bus_segs:
                mode = " + ".join(bus_segs)
            else:
                # 无公交段 → 纯步行方案
                ws = tr.get("segments", [{}])[0].get("walking") or {}
                mode = f"步行{_fmt_km(ws.get('distance') or tr.get('walking_distance', ''))}"

        wd = _mcp_parse(await t_walk.ainvoke({"origin": o, "destination": d})) if t_walk else None
        if isinstance(wd, dict):
            path = (wd.get("route", {}).get("paths") or [{}])[0]
            walk_desc = f"步行 {_fmt_km(path.get('distance'))} · {_fmt_minutes(path.get('duration'))}"

        if not mode and not (isinstance(wd, dict) and wd.get("route", {}).get("paths")):
            return f"{origin}→{destination}：未查到路线，建议现场导航。"

        summary = (f"{origin}→{destination}：{mode} · {dur} · {dist}" if mode
                   else f"{origin}→{destination}：{walk_desc}")
        if mode and mode != "步行" + dist:
            summary += f" / 备选：{walk_desc}"

        transit_json = json.dumps({
            "from": po["name"], "to": pd["name"],
            "mode": mode or "步行", "duration": dur,
            "distance": dist,
        }, ensure_ascii=False)
        payload = f"{summary}\ntransit_from_prev: {transit_json}"
        _amap_cache_put(cache_key, payload)
        return payload
    except Exception as e:
        return f"交通查询异常（{type(e).__name__}），{origin}→{destination} 建议现场导航。"


M1_TOOLS = [search_travel_knowledge, list_supported_cities, search_web_info,
            calculate_budget, generate_packing_list, export_itinerary_pdf,
            plan_route_between_spots]
