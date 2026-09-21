"""
验证城市 ID 对自由行 API 有效
mddid=10065(北京) 10099(上海) 10035(成都) 应返回对应城市方案
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))

from crawler_mfw_v3 import get_mfw_cookies, fetch_free_travel_list

TESTS = [
    (10065, "北京"),
    (10099, "上海"),
    (10035, "成都"),
    (10156, "杭州"),
]

cookie = get_mfw_cookies()

for mddid, expect in TESTS:
    result = fetch_free_travel_list(cookie, mddid, page=1)
    print(f"\n=== mddid={mddid} 期望={expect} ===")
    if not result:
        print("  无返回!")
        continue
    plans = result["plans"]
    print(f"  返回 {len(plans)} 条, pagination={result['pagination']}")
    for p in plans[:6]:
        print(f"    [{p['plan_id']}] {p['title'][:36]}  loc={p['location']}")
