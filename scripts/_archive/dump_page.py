"""Dump 马蜂窝自由行列表页面 HTML 看实际结构"""
import os, time, json

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=edge_path,
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        viewport={"width": 1920, "height": 1080},
    )
    context.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
    page = context.new_page()
    
    # 预热
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(3)
    page.goto("https://www.mafengwo.cn/", wait_until="networkidle", timeout=20000)
    time.sleep(2)
    
    # 访问自由行列表，等更久（可能是动态渲染）
    print("访问自由行列表（等待动态渲染）...")
    page.goto("https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid=21536&page=1", wait_until="domcontentloaded", timeout=20000)
    time.sleep(8)  # 等 SPA 动态渲染完成
    
    html = page.content()
    print(f"Content len: {len(html)}")
    
    # 保存
    with open("scripts/mfw_dump.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("已保存到 scripts/mfw_dump.html")
    
    # 分析
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    
    print(f"\n=== HTML 结构分析 ===")
    print(f"Title: {page.title()}")
    
    # 找所有 a 标签里有数字 ID 的（马蜂窝链接模式）
    import re
    links_with_id = []
    for a in soup.select("a[href*='/gonglve/']"):
        href = a.get("href", "")
        text = a.get_text(strip=True)[:50]
        m = re.search(r"/(\d+)\.html", href)
        if m:
            links_with_id.append((m.group(1), text, href))
    
    print(f"\n有 gonglve 的 a 标签（带数字 ID）: {len(links_with_id)}")
    for pid, text, href in links_with_id[:10]:
        print(f"  #{pid}: {text[:40]}")
    
    # 找 div/data 属性里可能的产品卡片
    cards = soup.select("[class*='card'], [class*='product'], [class*='list'], [class*='item']")
    print(f"\n可能的卡片/列表元素: {len(cards)}")
    for c in cards[:5]:
        cls = c.get("class", [])
        print(f"  class={cls}, children={len(c.find_all(recursive=False))}, text={c.get_text(strip=True)[:60]}")
    
    # 看 __INITIAL_STATE__ 或 window 上的 JSON 数据
    print(f"\n=== 页面 JS 变量 ===")
    js_data = page.evaluate("""() => {
        const result = {};
        for (const key of Object.keys(window)) {
            const v = window[key];
            if (typeof v === 'object' && v !== null) {
                try {
                    const s = JSON.stringify(v);
                    if (s.length > 100 && s.length < 50000) {
                        result[key] = s.substring(0, 200);
                    }
                } catch(e) {}
            }
        }
        return result;
    }""")
    for k, v in list(js_data.items())[:20]:
        print(f"  window.{k}: {v[:100]}")
    
    # 看自由行专用接口调用
    print(f"\n=== 网络请求里有没有 JSON API ===")
    # 拦截 XHR/fetch
    page.evaluate("""() => {
        window.__api_responses = [];
        const origFetch = window.fetch;
        window.fetch = async function(...args) {
            const resp = await origFetch.apply(this, args);
            const url = args[0]?.toString() || args[0]?.url || '';
            if (url.includes('gonglve') || url.includes('ziyouxing') || url.includes('api')) {
                const clone = resp.clone();
                try {
                    const text = await clone.text();
                    window.__api_responses.push({url, text: text.substring(0, 500)});
                } catch(e) {}
            }
            return resp;
        };
    }""")
    
    # 再触发一次 API
    page.reload(wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)
    
    api_data = page.evaluate("() => window.__api_responses || []")
    print(f"  捕获到 API 响应: {len(api_data)} 个")
    for item in api_data[:5]:
        print(f"  URL: {item['url'][:100]}")
        print(f"  Data: {item['text'][:200]}")
        print()
    
    browser.close()
