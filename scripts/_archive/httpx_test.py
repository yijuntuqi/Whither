"""测试 httpx 能不能直接 GET 这个接口 —— 如果能就不需要 Playwright 了！"""
import httpx, json

headers = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.mafengwo.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# 先不带 Cookie 试试
url = "https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid=21536&page=1"
print(f"1. 不带 Cookie 请求...")
resp = httpx.get(url, headers=headers, timeout=15)
print(f"   Status: {resp.status_code}")
print(f"   有 probe.js: {'probe.js' in resp.text[:500]}")
print(f"   有 ret/html: {'ret' in resp.text and 'html' in resp.text[:100]}")

if resp.status_code == 200 and 'probe.js' not in resp.text[:500]:
    print("   ✅ 直接 httpx 就能拿到！（因为带了 Referer + X-Requested-With）")
    try:
        data = json.loads(resp.text)
        print(f"   ret={data.get('ret')}, html_len={len(data.get('html', ''))}")
    except:
        pass
else:
    # 用 Playwright 先建 cookie，再从 Playwright 拿 cookie 给 httpx
    print(f"\n2. 用 Playwright 预热 + 提取 Cookie 给 httpx...")
    
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=edge, headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=headers["User-Agent"], viewport={"width": 1920, "height": 1080})
        ctx.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
        page = ctx.new_page()
        
        import time
        page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        page.goto("https://www.mafengwo.cn/", wait_until="networkidle", timeout=20000)
        time.sleep(2)
        
        cookies = ctx.cookies()
        browser.close()
    
    print(f"   拿到 {len(cookies)} 个 cookies")
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    
    headers_with_cookie = {**headers, "Cookie": cookie_header}
    resp2 = httpx.get(url, headers=headers_with_cookie, timeout=15)
    print(f"\n3. 带 Cookie 请求...")
    print(f"   Status: {resp2.status_code}")
    print(f"   有 probe.js: {'probe.js' in resp2.text[:500]}")
    
    try:
        data = json.loads(resp2.text)
        print(f"   ✅ ret={data.get('ret')}, html_len={len(data.get('html', ''))}")
        
        # 解析里面的 HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(data.get("html", ""), "lxml")
        import re
        
        items = soup.select(".item.clearfix")
        print(f"\n   📋 本页方案数: {len(items)}")
        
        for item in items[:5]:
            link = item.select_one("a")
            href = link.get("href", "") if link else ""
            pid = re.search(r"/(\d+)\.html", href)
            title = item.select_one("h3")
            location = item.select_one(".location")
            views = item.select_one(".view")
            
            print(f"   ✅ #{pid.group(1) if pid else '?'} | {title.get_text(strip=True) if title else '?'} | {location.get_text(strip=True) if location else '?'} | {views.get_text(strip=True) if views else '?'}")
        
        # 分页
        pag = soup.select_one(".count")
        if pag:
            print(f"\n   📄 分页: {pag.get_text(strip=True)}")
            
    except json.JSONDecodeError as e:
        print(f"   ❌ 不是 JSON: {e}")
        print(f"   前 200: {resp2.text[:200]}")
