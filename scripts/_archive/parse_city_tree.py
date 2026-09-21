"""
解析 mdd_home.html，提取所有目的地（省份/国家 → 城市）层级
并区分国内 vs 国外
"""
import re, json
from pathlib import Path
from bs4 import BeautifulSoup

html = Path("data/probe_city/mdd_home.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "lxml")

# 提取所有 travel-scenic-spot 链接
pattern = re.compile(r"/travel-scenic-spot/mafengwo/(\d+)\.html")

records = []
for a in soup.find_all("a", href=pattern):
    m = pattern.search(a["href"])
    name = a.get_text(strip=True)
    if not name:
        continue
    # 去掉英文 <span class=en>
    name = re.sub(r"\s+", " ", name).strip()
    records.append({
        "id": int(m.group(1)),
        "name": name,
        "parent_dt": None,
    })

print(f"总链接数(含重复): {len(records)}")

# 去重（同名同 id 只留一个），但保留第一次出现
seen = set()
uniq = []
for r in records:
    key = (r["id"], r["name"].split()[0])
    if r["id"] not in seen:
        seen.add(r["id"])
        # name 可能带英文，取中文部分
        cn = r["name"].split()[0]
        r["name"] = cn
        uniq.append(r)

print(f"唯一目的地数: {len(uniq)}")

# 找省份分组：结构 <dt><a>省份</a></dt> ... <dd> 或同级 a 城市
# 定位国内省份列表区块
# dt 里的是省份
prov_in_dt = []
for dt in soup.find_all("dt"):
    a = dt.find("a", href=pattern)
    if a:
        m = pattern.search(a["href"])
        prov_in_dt.append({"id": int(m.group(1)), "name": a.get_text(strip=True)})

print(f"\n省份/大区(dt)数: {len(prov_in_dt)}")
for p in prov_in_dt:
    print(f"  {p['id']:6d}  {p['name']}")

# 打印前 80 个唯一目的地，看分布
print(f"\n前 80 个唯一目的地:")
for r in uniq[:80]:
    print(f"  {r['id']:6d}  {r['name']}")

Path("data/probe_city").mkdir(parents=True, exist_ok=True)
Path("data/probe_city/all_destinations_raw.json").write_text(
    json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"\n💾 保存原始目的地: data/probe_city/all_destinations_raw.json")
