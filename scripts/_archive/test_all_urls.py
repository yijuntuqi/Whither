"""测试：哪些马蜂窝页面能直接爬？哪些有反爬？"""
import httpx, json, time

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

tests = [
    ("① 自由行列表（原以为无校验）", "https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid=21536&page=1"),
    ("② 自由行分类首页", "https://www.mafengwo.cn/gonglve/ziyouxing/"),
    ("③ 自由行详情页（静态）", "https://www.mafengwo.cn/gonglve/ziyouxing/26870.html"),
    ("④ 目的地首页", "https://www.mafengwo.cn/mdd"),
    ("⑤ 目的地-北京", "https://www.mafengwo.cn/mdd/citylist/21536.html"),
    ("⑥ 游记首页", "https://www.mafengwo.cn/yj/"),
    ("⑦ 首页", "https://www.mafengwo.cn/"),
]

client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0)

for label, url in tests:
    try:
        start = time.time()
        resp = client.get(url)
        elapsed = time.time() - start
        ct = resp.headers.get('content-type', '?')
        probe = 'probe.js' in resp.text
        init_state = '__INITIAL_STATE__' in resp.text or '__NUXT__' in resp.text
        
        status = "✅" if resp.status_code == 200 and not probe else ("🟡" if probe else "❌")
        print(f"{status} {label}")
        print(f"   {resp.status_code} | {elapsed:.1f}s | {ct[:30]} | len={len(resp.text)}")
        if probe:
            print(f"   ⚠️ 有 probe.js 反爬！")
        if init_state:
            print(f"   💡 有 __INITIAL_STATE__，可正则提取 JSON")
        print()
    except Exception as e:
        print(f"❌ {label}: {e}\n")

client.close()
