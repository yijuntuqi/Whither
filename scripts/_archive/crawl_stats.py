"""统计爬取结果"""
import json
from pathlib import Path

d = Path("data/crawled/free_travels")
files = sorted(d.glob("*.json"))

total_plans = 0
empty = []
stats = []
for f in files:
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        n = data.get("total_plans", 0)
        total_plans += n
        stats.append((f.stem, n))
        if n == 0:
            empty.append(f.stem)
    except Exception as e:
        empty.append(f"{f.stem}(parse_err)")

print(f"城市文件数: {len(files)}")
print(f"总方案数: {total_plans}")
print(f"空/异常: {empty if empty else '无'}")
print()
print("各城市方案数:")
for name, n in sorted(stats, key=lambda x: -x[1]):
    print(f"  {name:8s} {n}")
