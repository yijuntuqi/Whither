"""Playwright + Edge 马蜂窝测试 - 加足够等待"""
import os, time

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=edge_path,
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        viewport={"width": 1920, "height": 1080},
    )
    context.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
    page = context.new_page()

    # 预热 + 等 probe.js 执行（先访问一次，让 cookie 生效）
    print("预热马蜂窝首页...")
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)  # 等 probe.js 执行
    
    print(f"  Title: {page.title()}")
    html = page.content()
    print(f"  Content len: {len(html)}")
    print(f"  有 probe.js: {'probe.js' in html[:3000]}")
    
    # 再访问一次（probe 应该已经过了）
    print("\n再访问首页（probe 应该已过）...")
    page.goto("https://www.mafengwo.cn/", wait_until="networkidle", timeout=20000)
    time.sleep(2)
    print(f"  Title: {page.title()}")
    html = page.content()
    print(f"  Content len: {len(html)}")
    print(f"  probe.js: {'probe.js' in html[:3000]}")
    
    # 访问自由行列表
    print("\n访问自由行列表...")
    page.goto("https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid=21536&page=1", wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)
    print(f"  Title: {page.title()}")
    html = page.content()
    print(f"  Content len: {len(html)}")
    print(f"  probe.js: {'probe.js' in html[:3000]}")
    
    # 检查有没有 JSON 数据
    has_state = '__INITIAL_STATE__' in html or '__NUXT__' in html
    print(f"  有 INITIAL_STATE/NUXT: {has_state}")
    
    # 打印部分内容看有没有真实数据
    if len(html) > 5000:
        # 找页面里的城市名称
        import re
        titles = re.findall(r'<h[1-3][^>]*>([^<]{5,})</h[1-3]>', html)
        print(f"  页面标题元素: {titles[:5]}")
    
    # 检查 cookies
    cookies = context.cookies()
    print(f"\n  Cookies ({len(cookies)} 个):")
    for c in cookies[:5]:
        print(f"    {c['name']}: {c['value'][:30]}...")

    browser.close()
    print("\n✅ 测试完成")
