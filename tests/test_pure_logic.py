"""
P2-3：纯逻辑单元测试（不调用任何外部 API）
- calculate_budget：分类汇总 / 占比 / qty / 未知分类兜底
- _packing_rules：天气与活动分支
- render_html：结构渲染 / XSS 转义 / 空输入容错
"""
import json

import pytest

from backend.app.agent.tools import calculate_budget, _packing_rules
from backend.app.pdf.template import render_html


# ============ calculate_budget ============

def _run_budget(items):
    """@tool 包装的对象：直接调底层函数"""
    return calculate_budget.func(items)


def test_budget_basic_totals():
    out = _run_budget([
        {"category": "交通", "name": "高铁票", "amount": 720, "qty": 1},
        {"category": "门票", "name": "景区门票", "amount": 100, "qty": 2},
    ])
    assert "总计 920 元" in out
    # budget_json 可供 PDF 图表使用
    chart = json.loads(out.split("budget_json: ", 1)[1])
    assert chart["total"] == 920
    assert chart["by_category"]["交通"] == 720
    assert chart["by_category"]["门票"] == 200


def test_budget_percentages_sum_to_100():
    out = _run_budget([
        {"category": "交通", "name": "a", "amount": 500},
        {"category": "住宿", "name": "b", "amount": 300},
        {"category": "餐饮", "name": "c", "amount": 200},
    ])
    pcts = [float(line.split("%")[0][-4:]) for line in out.splitlines()
            if line.endswith("%")]
    assert abs(sum(pcts) - 100.0) < 0.1


def test_budget_unknown_category_falls_back():
    out = _run_budget([
        {"category": "瞎写的分类", "name": "x", "amount": 80},
        {"category": "其他", "name": "y", "amount": 20},
    ])
    assert "总计 100 元" in out
    chart = json.loads(out.split("budget_json: ", 1)[1])
    assert chart["by_category"]["其他"] == 100


def test_budget_qty_defaults_to_one():
    out = _run_budget([{"category": "餐饮", "name": "火锅", "amount": 150}])
    chart = json.loads(out.split("budget_json: ", 1)[1])
    assert chart["by_category"]["餐饮"] == 150


def test_budget_zero_and_empty():
    out = _run_budget([])
    assert "总计 0 元" in out
    chart = json.loads(out.split("budget_json: ", 1)[1])
    assert chart["total"] == 0
    assert chart["by_category"] == {}


# ============ _packing_rules ============

def test_packing_base_items_always_present():
    items = _packing_rules(1, "", "", "")
    assert "身份证/护照" in items
    assert "手机+充电器" in items


def test_packing_winter_branch():
    items = _packing_rules(2, "冬季", "零下20度有雪", "")
    assert "羽绒服/厚外套" in items
    assert "防滑雪地靴" in items
    assert "帽子围巾手套" in items


def test_packing_rain_branch():
    items = _packing_rules(2, "", "阵雨", "")
    assert "折叠伞/雨衣" in items
    assert "防水鞋" in items


def test_packing_summer_branch():
    items = _packing_rules(2, "夏季", "高温晴热", "")
    assert "防晒霜(SPF50)" in items
    assert "遮阳帽/太阳镜" in items


def test_packing_hiking_and_seaside_and_photo():
    items = _packing_rules(3, "", "", "徒步 海边 拍照")
    assert "登山杖/护膝" in items
    assert "泳衣泳镜" in items
    assert "三脚架/自拍杆" in items


def test_packing_long_trip_extras():
    short = _packing_rules(2, "", "", "")
    long = _packing_rules(5, "", "", "")
    assert "便携洗衣液" not in short
    assert "便携洗衣液" in long
    assert "零食" in long


# ============ render_html ============

def _sample_itinerary():
    return {
        "title": "成都2日游",
        "origin": "北京",
        "destination": "成都",
        "start_date": "2026-10-01",
        "days": [
            {"day": 1, "date": "2026-10-01", "items": [
                {"time": "09:00", "type": "交通", "name": "G89 北京西→成都东",
                 "duration": "7小时", "cost": 720, "note": "二等座"},
                {"time": "16:00", "type": "景点", "name": "宽窄巷子",
                 "duration": "2小时", "cost": 0, "note": "免费"},
            ]},
            {"day": 2, "date": "2026-10-02", "items": [
                {"time": "10:00", "type": "餐饮", "name": "火锅",
                 "duration": "1.5小时", "cost": 150},
            ]},
        ],
        "packing": ["身份证/护照", "防晒霜(SPF50)"],
        "references": ["https://www.mafengwo.cn/gonglve/ziyouxing/xxx.html"],
    }


def test_render_contains_core_sections():
    html = render_html(_sample_itinerary())
    assert "<title>成都2日游</title>" in html
    assert "北京" in html and "成都" in html
    assert "Day 1" in html and "Day 2" in html
    assert "G89 北京西→成都东" in html
    assert "宽窄巷子" in html
    # 预算面板（从 items.cost 汇总：720+0+150=870）
    assert "870" in html
    # 打包清单 + 参考链接
    assert "防晒霜(SPF50)" in html
    assert "https://www.mafengwo.cn/gonglve/ziyouxing/xxx.html" in html


def test_render_train_badge():
    html = render_html(_sample_itinerary())
    # G 开头车次应有车次徽章
    assert 'class="train-no">G89</span>' in html


def test_render_escapes_html_injection():
    data = _sample_itinerary()
    data["title"] = "<script>alert(1)</script>"
    html = render_html(data)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_empty_and_minimal_input():
    # 空 dict 不炸
    html = render_html({})
    assert "<html" in html
    # 只有标题
    html = render_html({"title": "随便走走"})
    assert "随便走走" in html


def test_render_bad_cost_is_tolerated():
    data = _sample_itinerary()
    data["days"][0]["items"][1]["cost"] = "不知道"
    html = render_html(data)
    assert "宽窄巷子" in html
