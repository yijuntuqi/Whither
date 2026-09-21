"""
探测省份/国家目的地页，确认能拿到该省下属城市
海南 12938 / 云南 12711 / 美国 10062
"""
import time, re
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
LINK_RE = re.compile(r"/travel-scenic-spot/mafengwo/(\d+)\.html")

TESTS = [(12938, "海南"), (12711, "云南"), (10062, "美国")]
OUT = Path("data/probe_city")

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path=EDGE, headless=True,
        args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1920, "height": 1080})
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    page = ctx.new_page()

    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
    time.sleep(2)

    for pid, pname in TESTS:
        url = f"https://www.mafengwo.cn/travel-scenic-spot/mafengwo/{pid}.html"
        print(f"\n=== {pname} ({pid}) ===")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            html = page.content()
            print(f"  title={page.title()}  len={len(html)}")
            (OUT / f"prov_{pid}_{pname}.html").write_text(html, encoding="utf-8")

            soup = BeautifulSoup(html, "lxml")
            # 所有目的地链接（排除自身）
            links = []
            for a in soup.find_all("a", href=LINK_RE):
                cid = int(LINK_RE.search(a["href"]).group(1))
                cname = a.get_text(strip=True)
                if cname and cid != pid and len(cname) <= 8:
                    links.append((cid, cname))
            # 去重
            seen = set(); uniq = []
            for cid, cname in links:
                if cid not in seen:
                    seen.add(cid); uniq.append((cid, cname))
            print(f"  页面内其他目的地链接 {len(uniq)} 个:")
            for cid, cname in uniq[:40]:
                print(f"    {cid:6d} {cname}")
        except Exception as e:
            print(f"  ERROR: {e}")

    browser.close()
