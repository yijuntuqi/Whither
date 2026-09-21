"""快速测试：马蜂窝自由行接口返回什么格式？"""
import httpx, json, time

mddid = 21536  # 北京
url = f"https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid={mddid}&page=1"

headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.mafengwo.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

print(f"请求: {url}")
start = time.time()
resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
elapsed = time.time() - start

print(f"状态码: {resp.status_code}")
print(f"耗时: {elapsed:.1f}s")
print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
print(f"Content-Length: {len(resp.text)} chars")

# 尝试 JSON
try:
    data = resp.json()
    print(f"\n✅ 返回 JSON!")
    print(f"Top-level keys: {list(data.keys())}")
    print(f"Structure:\n{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")
except json.JSONDecodeError:
    print(f"\n⚠️ 不是 JSON，前 1000 chars:")
    print(resp.text[:1000])
