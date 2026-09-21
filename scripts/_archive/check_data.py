"""统计爬虫数据质量"""
import json
from pathlib import Path

for f in Path("data/crawled/free_travels").glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    plans = d["plans"]
    has_detail = sum(1 for p in plans if p.get("content") and len(p["content"]) > 100)
    has_title = sum(1 for p in plans if p.get("title"))
    
    print(f"{f.name}: {len(plans)} 方案, 有标题={has_title}, 有详情={has_detail}")
    
    # 找最好的一条详情看看
    best = max(plans, key=lambda p: len(p.get("content", "")))
    if best.get("content"):
        print(f"  📖 最佳详情: #{best['plan_id']} | {best.get('title','?')[:40]}")
        print(f"  Content 长度: {len(best['content'])} chars")
        print(f"  前 300 字: {best['content'][:300]}...")
        print()
