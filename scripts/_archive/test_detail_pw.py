"""Playwright 直接访问详情页看能不能绕过 WAF"""
from playwright.sync_api import sync_playwright
import time, re, json

edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=edge, headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1920, "height": 1080})
    ctx.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
    page = ctx.new_page()
    
    # 预热
    print("预热...")
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(3)
    page.goto("https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid=21536&page=1", wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)
    print(f"列表页 title: {page.title()[:50]}")
    
    # 直接导航到详情页
    detail_url = "https://www.mafengwo.cn/gonglve/ziyouxing/157345.html"
    print(f"\n访问详情页: {detail_url}")
    page.goto(detail_url, wait_until="networkidle", timeout=20000)
    time.sleep(5)
    
    print(f"Title: {page.title()}")
    html = page.content()
    print(f"Content len: {len(html)}")
    
    if "probe.js" in html[:500] or "WAF" in html[:2000] or "中断" in html[:500]:
        print("❌ 还是被拦截了")
    else:
        print("✅ 绕过 WAF！")
    
    # 找内容
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1")
    if title_el:
        print(f"\n  Title: {title_el.get_text(strip=True)[:60]}")
    
    # 尝试抓正文
    for selector in [".product-detail", ".gyl-detail", ".itinerary-content", 
                     ".gyl-content", "article", ".product-content"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text("\n", strip=True)
            if len(text) > 200:
                print(f"  ✅ 找到正文 ({len(text)} chars)")
                print(f"  {text[:200]}...")
                break
    
    browser.close()
