"""Dump 一个马蜂窝自由行详情页看能不能拿到内容"""
import httpx, json, time
from playwright.sync_api import sync_playwright
from pathlib import Path

edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"

# Playwright 预热拿 cookie
print("拿 Cookie...")
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=edge, headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1920, "height": 1080})
    ctx.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
    page = ctx.new_page()
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(3)
    page.goto("https://www.mafengwo.cn/", wait_until="networkidle", timeout=20000)
    time.sleep(2)
    cookies = ctx.cookies()
    browser.close()

cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
print(f"✅ {len(cookies)} cookies")

# 用 httpx GET 详情页
url = "https://www.mafengwo.cn/gonglve/ziyouxing/157345.html"
headers = {"User-Agent": UA, "Cookie": cookie_str, "Referer": "https://www.mafengwo.cn/"}

resp = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
print(f"\nGET {url}")
print(f"Status: {resp.status_code}, Len: {len(resp.text)}")
print(f"有 probe.js: {'probe.js' in resp.text[:500]}")

# 保存 HTML
Path("scripts/detail_dump.html").write_text(resp.text, encoding="utf-8")
print(f"已保存到 scripts/detail_dump.html")

# 简单分析
from bs4 import BeautifulSoup
soup = BeautifulSoup(resp.text, "lxml")

title_el = soup.select_one("h1, .product-title, .gyl-title, h2, .title")
content_el = soup.select_one(".product-detail, .gyl-detail, .itinerary, .content, .gyl-content, article")

print(f"\nTitle: {title_el.get_text(strip=True)[:80] if title_el else '❌ 没找到'}")
print(f"Content 元素: {'✅' if content_el else '❌ 没找到'}")

# 列所有可能的容器
print("\n页面里可能的容器 class:")
for el in soup.find_all(["div", "article", "section"], limit=30):
    cls = el.get("class", [])
    if cls and any(k in " ".join(cls).lower() for k in ["content", "detail", "body", "text", "article", "main", "product", "gyl"]):
        text = el.get_text(strip=True)[:60]
        print(f"  .{' .'.join(cls)[:40]}... text={text}")
