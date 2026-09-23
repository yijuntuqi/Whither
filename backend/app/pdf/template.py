"""
行程手册 HTML 模板（杂志级排版，纯 CSS 零外部依赖）
- 封面横幅：标题/路线/日期/总预算/首站先酒店标记
- 偏好摘要卡：出行节奏/预算/酒店/餐饮/交通偏好
- 逐日时间线：天气卡 → 12306车次卡(含车次号/站点/票价) / 景点卡 / 餐饮住宿卡
  - first_stop_hotel=true 时不显示绝对时间，只显示间隔
  - first_stop_hotel=false 时保留绝对时间
- 酒店区块：每日住宿推荐
- 预算区：明细表 + conic-gradient 饼图
- 打包清单：双栏 checklist（兼容字符串/数组）
- A4 打印分页优化
"""
import html as html_mod
import json

# 品牌色系
BRAND = {
    "primary": "#0e7c7b",    # 旅行青
    "accent": "#f4795b",     # 珊瑚橙
    "dark": "#1d3557",
    "light": "#f1f7f7",
    "muted": "#6c757d",
    "sky": "#48cae4",
    "hotel": "#8e6bbf",
}

# 行程 item type → 颜色/图标（图标为内联 SVG，容器无彩色 emoji 字体也不会出现豆腐块）
TYPE_STYLE = {
    "交通": ("#0e7c7b", "train"),
    "景点": ("#f4795b", "pin"),
    "餐饮": ("#e6a23c", "bowl"),
    "住宿": ("#8e6bbf", "bed"),
    "购物": ("#d81b60", "bag"),
    "自由": ("#6c757d", "compass"),
}

TYPE_TO_BUDGET_CAT = {"交通": "交通", "景点": "门票", "餐饮": "餐饮", "住宿": "住宿",
                      "购物": "其他", "自由": "其他"}

# ===== 内联 SVG 图标（24x24，线性风格，currentColor）=====
_SVG_PATHS = {
    "train": ('<rect x="5" y="3" width="14" height="14" rx="3"/>'
              '<path d="M5 11h14"/><path d="M9 6.5h6"/>'
              '<circle cx="8.5" cy="14.5" r=".8" fill="currentColor" stroke="none"/>'
              '<circle cx="15.5" cy="14.5" r=".8" fill="currentColor" stroke="none"/>'
              '<path d="M7 20l-2 1.5M17 20l2 1.5"/>'),
    "pin": ('<path d="M12 21s-7-6.3-7-11a7 7 0 1 1 14 0c0 4.7-7 11-7 11z"/>'
            '<circle cx="12" cy="10" r="2.5"/>'),
    "bowl": ('<path d="M4 11h16a8 8 0 0 1-16 0z"/><path d="M8 11V4"/>'
             '<path d="M11 8V5"/>'),
    "bed": ('<path d="M3 18v-7"/><path d="M3 13h18v5"/>'
            '<path d="M7 13v-3a2 2 0 0 1 2-2h6"/>'),
    "bag": ('<path d="M6 8h12l-1 12H7z"/><path d="M9 8a3 3 0 0 1 6 0"/>'),
    "compass": ('<circle cx="12" cy="12" r="9"/>'
                '<path d="M15.5 8.5l-2 5-5 2 2-5z"/>'),
    "sun": ('<circle cx="12" cy="12" r="4"/>'
            '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4'
            'M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    "cloud": ('<path d="M7 18h10a4.5 4.5 0 0 0 1-8.9A6 6 0 0 0 6.5 11 4 4 0 0 0 7 18z"/>'),
    "cloud-rain": ('<path d="M7 15h10a4.5 4.5 0 0 0 1-8.9A6 6 0 0 0 6.5 8 4 4 0 0 0 7 15z"/>'
                   '<path d="M8 18l-1 3M12 18l-1 3M16 18l-1 3"/>'),
    "thermometer": ('<path d="M10 13.5V5a2 2 0 1 1 4 0v8.5a4 4 0 1 1-4 0z"/>'),
    "bulb": ('<path d="M9 18h6M10 21h4"/>'
             '<path d="M12 3a6 6 0 0 0-3.5 10.9c.7.6 1 1.2 1 2.1h5c0-.9.4-1.5 1-2.1A6 6 0 0 0 12 3z"/>'),
    "calendar": ('<rect x="3" y="5" width="18" height="16" rx="2"/>'
                 '<path d="M3 9.5h18M8 3v4M16 3v4"/>'),
    "wallet": ('<path d="M3 7a2 2 0 0 1 2-2h12v3"/><path d="M3 7v10a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-9H5"/>'
               '<path d="M16.5 13h.01"/>'),
    "package": ('<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/>'
                '<path d="M12 13v8"/>'),
    "check-square": ('<rect x="4" y="4" width="16" height="16" rx="2"/>'
                     '<path d="M8.5 12.5l2.5 2.5 4.5-5"/>'),
    "target": ('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/>'
               '<circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>'),
    "building": ('<path d="M3 21V8l6-4v17"/><path d="M9 21V11h12v10"/>'
                 '<path d="M14.5 14h.01M18 14h.01M14.5 17.5h.01M18 17.5h.01"/>'),
    "route": ('<circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/>'
              '<path d="M8 18h6a3 3 0 0 0 0-6H10a3 3 0 0 1 0-6h6"/>'),
    "clock": ('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>'),
}


def _svg(name: str, size: int = 15, color: str = "currentColor", sw: float | int = 2) -> str:
    body = _SVG_PATHS.get(name, "")
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


def _esc(s) -> str:
    return html_mod.escape(str(s if s is not None else ""))


def _fmt_cost(cost) -> str:
    try:
        v = float(cost)
        return f"¥{v:.0f}" if v == int(v) else f"¥{v:.2f}"
    except (TypeError, ValueError):
        return ""


def _budget_summary(data: dict) -> dict:
    """从 days.items 的 cost 按 type 汇总预算"""
    cats: dict[str, float] = {}
    for day in data.get("days", []):
        for it in day.get("items", []):
            cat = TYPE_TO_BUDGET_CAT.get(it.get("type", ""), "其他")
            try:
                cats[cat] = cats.get(cat, 0) + float(it.get("cost") or 0)
            except (TypeError, ValueError):
                pass
    total = sum(cats.values())
    return {"by_category": cats, "total": total}


def _pie_css(cats: dict) -> str:
    """conic-gradient 饼图 + 图例"""
    palette = ["#0e7c7b", "#f4795b", "#e6a23c", "#8e6bbf", "#d81b60", "#90a4ae"]
    total = sum(cats.values()) or 1
    stops, legend, acc = [], [], 0.0
    for i, (cat, val) in enumerate(cats.items()):
        start = acc / total * 360
        acc += val
        end = acc / total * 360
        color = palette[i % len(palette)]
        if end - start < 360:
            stops.append(f"{color} {start:.1f}deg {end:.1f}deg")
        else:
            stops.append(f"{color} 0deg 360deg")
        pct = val / total * 100
        legend.append(
            f'<div class="lg-item"><span class="lg-dot" style="background:{color}"></span>'
            f'{_esc(cat)} <span class="lg-val">¥{val:,.0f} · {pct:.1f}%</span></div>'
        )
    pie = f'background: conic-gradient({", ".join(stops)});' if cats else "background:#eee;"
    return f'<div class="pie" style="{pie}"></div><div class="legend">{"".join(legend)}</div>'


# ===== 天气卡 =====

def _weather_card(weather) -> str:
    """每日天气卡（temp/condition/rain/tip）"""
    if not weather or not isinstance(weather, dict):
        return ""
    temp = weather.get("temp", "")
    cond = weather.get("condition", "")
    rain = weather.get("rain")
    tip = weather.get("tip", "")
    if rain or (cond and ("雨" in cond or "雪" in cond)):
        icon_name = "cloud-rain"
    elif cond and "多云" in cond:
        icon_name = "cloud"
    elif cond and "晴" in cond:
        icon_name = "sun"
    else:
        icon_name = "thermometer"
    parts = []
    if temp:
        parts.append(f'<span class="w-temp">{_esc(temp)}</span>')
    if cond:
        parts.append(f'<span class="w-cond">{_esc(cond)}</span>')
    if tip:
        parts.append(f'<span class="w-tip">{_svg("bulb", 13, BRAND["primary"])} {_esc(tip)}</span>')
    return (f'<div class="weather-card"><span class="w-icon">'
            f'{_svg(icon_name, 21, BRAND["primary"])}</span>{"".join(parts)}</div>')


# ===== 酒店区块 =====

def _hotel_section(hotels) -> str:
    """住宿推荐区块"""
    if not hotels or not isinstance(hotels, list):
        return ""
    cards = []
    for h in hotels:
        if not isinstance(h, dict):
            continue
        name = h.get("name", "")
        if not name:
            continue
        price = _fmt_cost(h.get("price"))
        addr = h.get("address", "")
        reason = h.get("reason", "")
        checkin = h.get("checkin_date", "")
        meta_parts = []
        if price:
            meta_parts.append(f'<span class="h-price">{price}/晚</span>')
        if checkin:
            meta_parts.append(f'<span class="h-date">入住 {_esc(checkin)}</span>')
        if addr:
            meta_parts.append(
                f'<span class="h-addr">{_svg("pin", 12, BRAND["muted"])} {_esc(addr)}</span>')
        reason_html = f'<div class="h-reason">推荐：{_esc(reason)}</div>' if reason else ""
        cards.append(
            f'<div class="hotel-card"><div class="h-name">{_svg("building", 15, BRAND["hotel"])} '
            f'{_esc(name)}</div>'
            f'<div class="h-meta">{"".join(meta_parts)}</div>{reason_html}</div>'
        )
    if not cards:
        return ""
    return (f'<div class="hotel-section"><div class="hs-title">'
            f'{_svg("building", 15, BRAND["hotel"])} 住宿推荐</div>{"".join(cards)}</div>')


# ===== 12306 车次详情卡 =====

def _train_detail(it: dict) -> str:
    """12306 跨城火车详情卡：车次号/出发→到达站/发到时间/时长/座位类型/票价"""
    info = it.get("train_info")
    # 优先用结构化 train_info
    if isinstance(info, dict) and info:
        parts = []
        if info.get("train_no"):
            parts.append(f'<span class="train-no">{_esc(info["train_no"])}</span>')
        fs, ts = info.get("from_station", ""), info.get("to_station", "")
        if fs or ts:
            parts.append(f'<span class="train-route">{_esc(fs)} → {_esc(ts)}</span>')
        dep, arr = info.get("departure_time", ""), info.get("arrival_time", "")
        if dep or arr:
            parts.append(f'<span class="train-time">{_esc(dep)} - {_esc(arr)}</span>')
        if info.get("duration"):
            parts.append(f'<span class="train-dur">{_esc(info["duration"])}</span>')
        if info.get("seat_class"):
            parts.append(f'<span class="train-seat">{_esc(info["seat_class"])}</span>')
        if info.get("price"):
            parts.append(f'<span class="train-price">{_fmt_cost(info["price"])}</span>')
        return f'<div class="train-detail">{"".join(parts)}</div>'
    # 兼容旧格式：从 name/note/cost 提取
    name = it.get("name", "")
    if not name or not any(c in name[:6] for c in "GDC"):
        return ""
    parts = []
    train_no = name.split()[0] if name else ""
    if train_no:
        parts.append(f'<span class="train-no">{_esc(train_no)}</span>')
    if name:
        parts.append(f'<span class="train-route">{_esc(name)}</span>')
    if it.get("duration"):
        parts.append(f'<span class="train-dur">{_esc(it["duration"])}</span>')
    note = it.get("note", "")
    if note:
        parts.append(f'<span class="train-seat">{_esc(note)}</span>')
    cost = _fmt_cost(it.get("cost"))
    if cost:
        parts.append(f'<span class="train-price">{cost}</span>')
    return f'<div class="train-detail">{"".join(parts)}</div>'


# ===== 景点间交通行 =====

def _transit_badge(tr) -> str:
    """景点卡上方的『从前一站到本站』交通信息行（灰色小字）"""
    if not isinstance(tr, dict) or not (tr.get("mode") or tr.get("duration")):
        return ""
    bits = [tr.get("mode", "")]
    if tr.get("duration"):
        bits.append(tr["duration"])
    if tr.get("distance"):
        bits.append(tr["distance"])
    if tr.get("cost"):
        bits.append(f"约{tr['cost']}元")
    return (f'<div class="transit-line">{_svg("route", 12, BRAND["muted"])} '
            f'前往本站：{_esc(" · ".join(b for b in bits if b))}</div>')


# ===== 逐日时间线 =====

def _timeline_items(items: list, first_stop_hotel: bool = False) -> str:
    """逐日时间线 items
    first_stop_hotel=True 时不显示绝对时间，改为间隔标记（从酒店出发/⏱ 间隔）
    """
    cards = []
    for idx, it in enumerate(items):
        color, icon_name = TYPE_STYLE.get(it.get("type", ""), TYPE_STYLE["自由"])
        cost = _fmt_cost(it.get("cost"))
        note = it.get("note") or ""
        name = it.get("name", "")

        # 时间显示逻辑
        if first_stop_hotel:
            if idx == 0:
                time_label = "酒店出发"
            else:
                tr = it.get("transit_from_prev") or {}
                interval = tr.get("duration", "")
                time_label = (f'<span class="tl-interval">{_svg("clock", 11, BRAND["muted"])} '
                              f'{_esc(interval)}</span>' if interval else "")
        else:
            time_label = _esc(it.get("time", ""))

        # 12306 车次卡详情
        train_html = _train_detail(it) if it.get("type") == "交通" else ""
        # 有结构化 train_info 时车次卡已含全部信息，不再渲染通用名称/元信息行，避免重复
        struct_train = (it.get("type") == "交通"
                        and isinstance(it.get("train_info"), dict)
                        and bool(it.get("train_info")))
        if struct_train:
            body = train_html
        else:
            body = f"""
            {_transit_badge(it.get('transit_from_prev'))}
            {train_html}
            <div class="tl-head"><span class="tl-name">{_esc(name)}</span>
              {f'<span class="tl-cost">{cost}</span>' if cost else ''}</div>
            <div class="tl-meta">{_esc(it.get('type', ''))} · {_esc(it.get('duration', ''))}
              {f' · <span class="tl-note">{_esc(note)}</span>' if note else ''}</div>"""

        cards.append(f"""
        <div class="tl-item">
          <div class="tl-time">{time_label}</div>
          <div class="tl-dot" style="background:{color}">{_svg(icon_name, 15, "#fff", 2)}</div>
          <div class="tl-card" style="border-left-color:{color}">
            {body}
          </div>
        </div>""")
    return "".join(cards)


# ===== 打包清单（兼容字符串/数组）=====

def _packing_list_html(packing) -> str:
    """打包清单 HTML（兼容字符串按行切分 / 数组直接渲染）"""
    if not packing:
        return ""
    if isinstance(packing, str):
        items = [line.strip().lstrip("☐☐☐ ").strip() for line in packing.split("\n") if line.strip()]
    elif isinstance(packing, list):
        items = [str(p).strip() for p in packing if p]
    else:
        return ""
    return "".join(
        f'<div class="pk-item">{_svg("check-square", 14, BRAND["primary"])} {_esc(p)}</div>'
        for p in items if p)


# ===== 偏好摘要卡 =====

def _profile_summary(data: dict) -> str:
    """出行偏好摘要卡"""
    profile = data.get("travel_profile")
    if not profile or not isinstance(profile, dict):
        return ""
    fields = [
        ("出行节奏", profile.get("pace", "")),
        ("预算", profile.get("budget", "")),
        ("酒店偏好", profile.get("hotel_pref", "")),
        ("餐饮偏好", profile.get("food", "")),
        ("交通偏好", profile.get("transport", "")),
        ("特殊需求", profile.get("special", "")),
    ]
    chips = []
    for label, val in fields:
        if val:
            chips.append(
                f'<div class="pf-chip"><span class="pf-label">{_esc(label)}</span>'
                f'<span class="pf-val">{_esc(val)}</span></div>'
            )
    if not chips:
        return ""
    return (f'<div class="profile-card"><div class="pf-title">'
            f'{_svg("target", 15, BRAND["dark"])} 出行偏好</div>{"".join(chips)}</div>')


# ===== 主渲染 =====

def render_html(data: dict) -> str:
    """itinerary dict → 完整 HTML"""
    title = _esc(data.get("title", "旅行行程"))
    origin = _esc(data.get("origin", ""))
    dest = _esc(data.get("destination", ""))
    start = _esc(data.get("start_date", ""))
    refs = data.get("references", []) or []
    first_stop_hotel = data.get("first_stop_hotel", False)

    days_html = []
    for day in data.get("days", []):
        dlabel = f"Day {day.get('day', '')}"
        ddate = day.get("date", "")
        weather_html = _weather_card(day.get("weather"))
        hotel_html = _hotel_section(day.get("hotels"))
        days_html.append(f"""
      <section class="day">
        <div class="day-head">
          <span class="day-num">{_esc(dlabel)}</span>
          <span class="day-date">{_esc(ddate)}</span>
          <div class="day-line"></div>
        </div>
        {weather_html}
        {_timeline_items(day.get('items', []), first_stop_hotel)}
        {hotel_html}
      </section>""")

    budget = _budget_summary(data)
    total_str = f"¥{budget['total']:,.0f}" if budget["total"] else ""
    packing_html = _packing_list_html(data.get("packing", []))
    refs_html = "".join(
        f'<div class="ref-item">· <a href="{_esc(r)}">{_esc(r)}</a></div>' for r in refs)
    profile_html = _profile_summary(data)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  .ic {{ vertical-align: -.18em; flex-shrink: 0; }}
  .tl-interval {{ display: inline-flex; align-items: center; gap: 2px; }}
  body {{ font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
         color: #2b2b2b; font-size: 11pt; line-height: 1.55; }}
  @page {{ size: A4; margin: 14mm 12mm; }}

  /* ===== 封面横幅 ===== */
  .cover {{ background: linear-gradient(135deg, {BRAND['dark']} 0%, {BRAND['primary']} 100%);
           color: #fff; border-radius: 14px; padding: 34px 30px 28px; margin-bottom: 26px;
           position: relative; overflow: hidden; }}
  .cover::after {{ content: ""; position: absolute; top: -30px; right: -30px; width: 120px;
                   height: 120px; border-radius: 50%; background: rgba(255,255,255,.08); }}
  .cover::before {{ content: ""; position: absolute; bottom: -40px; right: 40px; width: 80px;
                    height: 80px; border-radius: 50%; background: rgba(255,255,255,.06); }}
  .cover .kicker {{ letter-spacing: 4px; font-size: 9pt; opacity: .85; position: relative; z-index: 1; }}
  .cover h1 {{ font-size: 26pt; margin: 8px 0 14px; font-weight: 700; position: relative; z-index: 1; }}
  .cover .route {{ font-size: 14pt; font-weight: 300; position: relative; z-index: 1; }}
  .cover .route b {{ font-weight: 700; }}
  .cover .route .arrow {{ color: {BRAND['accent']}; margin: 0 10px; }}
  .cover .meta {{ display: flex; gap: 14px; margin-top: 18px; font-size: 10pt; opacity: .92;
                 flex-wrap: wrap; position: relative; z-index: 1; }}
  .cover .meta .chip {{ background: rgba(255,255,255,.16); padding: 5px 14px; border-radius: 999px; }}
  .cover .meta .chip b {{ color: #ffd9cc; }}

  /* ===== 偏好摘要卡 ===== */
  .profile-card {{ background: {BRAND['light']}; border-radius: 12px; padding: 14px 20px; margin-bottom: 22px;
                  border-left: 4px solid {BRAND['primary']}; }}
  .pf-title {{ font-size: 11pt; font-weight: 700; color: {BRAND['dark']}; margin-bottom: 8px; }}
  .pf-chip {{ display: inline-flex; gap: 6px; align-items: center; background: #fff;
             border-radius: 999px; padding: 3px 12px; margin: 3px 4px; font-size: 9.5pt;
             border: 1px solid #e0e8e8; }}
  .pf-label {{ color: {BRAND['muted']}; }}
  .pf-val {{ color: {BRAND['dark']}; font-weight: 600; }}

  /* ===== 天气卡 ===== */
  .weather-card {{ display: flex; align-items: center; gap: 14px; border-radius: 10px;
                  padding: 8px 16px; margin-bottom: 12px; background: linear-gradient(135deg,
                  {BRAND['sky']}18 0%, {BRAND['light']} 100%); border: 1px solid {BRAND['sky']}30; }}
  .w-icon {{ font-size: 20px; }}
  .w-temp {{ font-size: 11pt; font-weight: 700; color: {BRAND['dark']}; }}
  .w-cond {{ font-size: 10pt; color: {BRAND['muted']}; }}
  .w-tip {{ font-size: 9pt; color: {BRAND['primary']}; margin-left: auto; }}

  /* ===== 逐日时间线 ===== */
  .day {{ margin-bottom: 24px; page-break-inside: avoid; }}
  .day-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
  .day-num {{ background: {BRAND['primary']}; color: #fff; font-weight: 700; font-size: 12pt;
             padding: 4px 14px; border-radius: 8px; }}
  .day-date {{ color: {BRAND['muted']}; font-size: 10pt; }}
  .day-line {{ flex: 1; height: 2px; background: linear-gradient(90deg, {BRAND['primary']}44, transparent); }}

  .tl-item {{ display: flex; gap: 12px; margin: 0 0 10px 8px; page-break-inside: avoid; }}
  .tl-time {{ width: 62px; text-align: right; color: {BRAND['muted']}; font-size: 9pt;
             padding-top: 9px; flex-shrink: 0; font-variant-numeric: tabular-nums; }}
  .tl-dot {{ width: 30px; height: 30px; border-radius: 50%; color: #fff; display: flex;
            align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0;
            margin-top: 3px; box-shadow: 0 0 0 3px {BRAND['light']}; }}
  .tl-card {{ flex: 1; background: #fff; border: 1px solid #e8ecef; border-left: 4px solid #ccc;
             border-radius: 10px; padding: 9px 14px; }}
  .tl-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }}
  .tl-name {{ font-weight: 700; font-size: 11pt; }}
  .tl-cost {{ color: {BRAND['accent']}; font-weight: 700; white-space: nowrap; }}
  .tl-meta {{ color: {BRAND['muted']}; font-size: 9.5pt; margin-top: 3px; }}
  .tl-note {{ color: #444; }}
  .transit-line {{ color: {BRAND['muted']}; font-size: 8.5pt; margin-bottom: 4px;
                  padding-bottom: 3px; border-bottom: 1px dashed #e3e8e8; }}

  /* ===== 12306 车次详情卡 ===== */
  .train-detail {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
                  background: {BRAND['primary']}0d; border-radius: 6px; padding: 6px 10px;
                  margin-bottom: 6px; }}
  .train-no {{ background: {BRAND['primary']}; color: #fff; font-size: 9pt; font-weight: 700;
              padding: 2px 10px; border-radius: 4px; }}
  .train-route {{ font-size: 10pt; font-weight: 600; color: {BRAND['dark']}; }}
  .train-time {{ font-size: 9pt; color: {BRAND['muted']}; font-variant-numeric: tabular-nums; }}
  .train-dur {{ font-size: 9pt; color: {BRAND['muted']}; }}
  .train-seat {{ font-size: 9pt; color: {BRAND['dark']}; background: {BRAND['accent']}1a;
                padding: 1px 8px; border-radius: 3px; }}
  .train-price {{ font-size: 10pt; font-weight: 700; color: {BRAND['accent']}; margin-left: auto; }}

  /* ===== 酒店区块 ===== */
  .hotel-section {{ margin: 12px 0 4px 50px; }}
  .hs-title {{ font-size: 10pt; font-weight: 700; color: {BRAND['hotel']}; margin-bottom: 6px; }}
  .hotel-card {{ background: {BRAND['hotel']}0a; border-left: 3px solid {BRAND['hotel']};
                 border-radius: 6px; padding: 8px 12px; margin-bottom: 6px; }}
  .h-name {{ font-size: 10.5pt; font-weight: 700; color: {BRAND['dark']}; }}
  .h-meta {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: 9pt; color: {BRAND['muted']}; margin-top: 3px; }}
  .h-price {{ color: {BRAND['accent']}; font-weight: 700; }}
  .h-reason {{ font-size: 9pt; color: #555; margin-top: 3px; }}

  /* ===== 预算 ===== */
  .panel {{ background: {BRAND['light']}; border-radius: 14px; padding: 20px 24px;
           margin: 26px 0; page-break-inside: avoid; }}
  .panel h2 {{ font-size: 14pt; color: {BRAND['dark']}; margin-bottom: 14px; }}
  .budget-flex {{ display: flex; gap: 30px; align-items: center; }}
  .pie {{ width: 130px; height: 130px; border-radius: 50%; flex-shrink: 0;
         box-shadow: inset 0 0 0 4px #fff; }}
  .legend {{ flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 7px 18px; }}
  .lg-item {{ display: flex; align-items: center; gap: 8px; font-size: 10pt; }}
  .lg-dot {{ width: 11px; height: 11px; border-radius: 3px; flex-shrink: 0; }}
  .lg-val {{ color: {BRAND['muted']}; margin-left: auto; font-variant-numeric: tabular-nums; }}
  .budget-total {{ margin-top: 14px; font-size: 12pt; }}
  .budget-total b {{ color: {BRAND['accent']}; font-size: 16pt; }}

  /* ===== 打包清单 ===== */
  .pk-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 22px; }}
  .pk-item {{ font-size: 10.5pt; padding: 3px 0; border-bottom: 1px dashed #d8e2e2; }}

  /* ===== 参考 ===== */
  .refs {{ margin-top: 22px; font-size: 9pt; color: {BRAND['muted']}; }}
  .ref-item a {{ color: {BRAND['primary']}; text-decoration: none; word-break: break-all; }}
  .foot {{ margin-top: 26px; text-align: center; color: {BRAND['muted']}; font-size: 9pt;
          letter-spacing: 2px; }}
</style>
</head>
<body>
  <div class="cover">
    <div class="kicker">WHITHER · 何之旅行手册</div>
    <h1>{title}</h1>
    <div class="route"><b>{origin}</b><span class="arrow">→</span><b>{dest}</b></div>
    <div class="meta">
      {f'<div class="chip">{_svg("calendar", 13, "#fff")} {start} 出发</div>' if start else ''}
      {f'<div class="chip">{_svg("wallet", 13, "#fff")} 总预算 <b>{total_str}</b></div>' if total_str else ''}
      <div class="chip">{_svg("package", 13, "#fff")} {len(data.get('days', []))} 天</div>
      {f'<div class="chip">{_svg("building", 13, "#fff")} 首站先到酒店</div>' if first_stop_hotel else ''}
    </div>
  </div>

  {profile_html}

  {''.join(days_html)}

  {f'''<div class="panel">
    <h2>{_svg("wallet", 17, BRAND["dark"])} 预算明细</h2>
    <div class="budget-flex">{_pie_css(budget['by_category'])}</div>
    <div class="budget-total">预估总计 <b>{total_str}</b>（人均）</div>
  </div>''' if budget['by_category'] else ''}

  {f'''<div class="panel">
    <h2>{_svg("package", 17, BRAND["dark"])} 打包清单</h2>
    <div class="pk-grid">{packing_html}</div>
  </div>''' if packing_html else ''}

  {f'''<div class="refs"><b>攻略参考</b>{refs_html}</div>''' if refs else ''}

  <div class="foot">— WHITHER · 何之 · 让每一次出发都从容 —</div>
</body>
</html>"""


def parse_itinerary_block(text: str) -> dict | None:
    """从 agent 回复中提取 ```itinerary ...``` 代码块并解析为 dict"""
    marker = "```itinerary"
    if marker not in text:
        return None
    block = text.split(marker, 1)[1]
    block = block.split("```", 1)[0].strip()
    # 去掉可能的语言标注行
    if block.startswith("json"):
        block = block[4:].strip()
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        return None
