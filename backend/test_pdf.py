"""M3.5 PDF 生成测试：样例 itinerary → HTML → PDF"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from backend.app.pdf.generator import generate_pdf
from backend.app.pdf.template import parse_itinerary_block

SAMPLE = {
    "title": "北京到天津一日游",
    "origin": "北京",
    "destination": "天津",
    "start_date": "2026-09-20",
    "days": [
        {"day": 1, "date": "2026-09-20", "items": [
            {"time": "06:27", "type": "交通", "name": "C2553 北京南→天津", "duration": "30分钟", "cost": 54.5, "note": "二等座"},
            {"time": "07:30", "type": "餐饮", "name": "老永胜包子（早餐）", "duration": "40分钟", "cost": 15, "note": "天津传统早餐"},
            {"time": "08:30", "type": "景点", "name": "意式风情区", "duration": "2小时", "cost": 0, "note": "免费·早晨人少适合拍照"},
            {"time": "10:45", "type": "景点", "name": "天津古文化街", "duration": "2小时", "cost": 0, "note": "泥人张·杨柳青年画"},
            {"time": "12:30", "type": "餐饮", "name": "狗不理总店午餐", "duration": "1小时", "cost": 88, "note": "三鲜包子套餐"},
            {"time": "14:00", "type": "景点", "name": "天津之眼摩天轮", "duration": "1.5小时", "cost": 70, "note": "建议提前购票"},
            {"time": "16:30", "type": "景点", "name": "五大道漫步", "duration": "1.5小时", "cost": 0, "note": "洋楼建筑群"},
            {"time": "18:30", "type": "交通", "name": "C2262 天津→北京南", "duration": "37分钟", "cost": 54.5, "note": "二等座"},
        ]}
    ],
    "budget_total": 282,
    "packing": ["身份证", "手机充电宝", "轻便背包", "防晒霜", "舒适的鞋", "少量现金"],
    "references": [
        "https://www.mafengwo.cn/gonglve/ziyouxing/320284.html",
        "https://www.mafengwo.cn/gonglve/ziyouxing/319032.html",
    ],
}

# 1. itinerary 块解析测试
import json as _json
block_text = f"前言blabla\n```itinerary\n{_json.dumps(SAMPLE, ensure_ascii=False)}\n```\n后续"
parsed = parse_itinerary_block(block_text)
assert parsed and parsed["title"] == SAMPLE["title"], "parse_itinerary_block 失败"
print("✅ itinerary 块解析 OK")

# 2. PDF 生成
pdf = generate_pdf(SAMPLE)
size_kb = pdf.stat().st_size / 1024
assert pdf.exists() and size_kb > 20, f"PDF 异常: {pdf} ({size_kb:.1f} KB)"
print(f"✅ PDF 生成 OK: {pdf} ({size_kb:.0f} KB)")
