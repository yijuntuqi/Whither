"""
探测马蜂窝城市索引页结构
目标：找到能列出所有城市 + mddId 的入口
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"

# 候选城市索引入口
CANDIDATES = [
    ("mdd_home", "https://www.mafengwo.cn/mdd/"),
    ("cy_index", "https://www.mafengwo.cn/cy/"),
    ("mdd_citylist_root", "https://www.mafengwo.cn/mdd/citylist/"),
    ("mdd_china", "https://www.mafengwo.cn/mdd/country/10065.html"),
]

OUT = Path("data/probe_city")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path=EDGE, headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1920, "height": 1080})
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    page = ctx.new_page()

    # 预热拿 cookie
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(2)
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(1)

    for name, url in CANDIDATES:
        print(f"\n=== {name}: {url} ===")
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
            print(f"  status: {resp.status if resp else '?'}")
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            title = page.title()
            html = page.content()
            print(f"  title: {title}")
            print(f"  html_len: {len(html)}")
            print(f"  has_probe: {'probe.js' in html[:2000]}")

            (OUT / f"{name}.html").write_text(html, encoding="utf-8")
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)

            # 看页面上有哪些指向 mdd 城市的链接
            links = page.eval_on_selector_all(
                "a[href]",
                """els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,20)}))
                    .filter(x => x.text && x.text.length <= 12)
                    .slice(0, 30)"""
            )
            citylike = [l for l in links if any(k in l["href"] for k in ["/mdd/", "/cy/", "/travel-scenic-spot/", "/citylist/"])]
            print(f"  city-like links (first 20):")
            for l in citylike[:20]:
                print(f"    {l['text']:12s} -> {l['href']}")

        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    browser.close()

print(f"\n✅ 探测文件保存到: {OUT.resolve()}")
