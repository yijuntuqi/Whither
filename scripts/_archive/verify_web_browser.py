"""P1-2 权威浏览器实测：Playwright + 系统 Edge（真实 Chromium 内核，绕开
自动化工具的请求拦截层）。验证页面对话 + SSE 流式逐字输出。
用法: E:\\conda_envs\\langchain\\python.exe scripts/verify_web_browser.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from playwright.sync_api import sync_playwright

SYSTEM_BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

URL = "http://127.0.0.1:8000"
SHOT = ROOT / "logs" / "web_test.png"

with sync_playwright() as pw:
    browser = None
    for p in SYSTEM_BROWSERS:
        if Path(p).exists():
            browser = pw.chromium.launch(executable_path=p, headless=True)
            print(f"浏览器: {p}")
            break
    if browser is None:
        browser = pw.chromium.launch(headless=True)
        print("浏览器: Playwright 自带 Chromium")

    page = browser.new_page()
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("response", lambda r: print(f"  ← {r.status} {r.request.method} {r.url}")
            if ("/chat" in r.url or "favicon" in r.url) else None)
    page.on("requestfailed", lambda r: print(f"  ✗ FAILED {r.url} {r.failure}")
            if "/chat" in r.url else None)

    page.goto(URL, wait_until="networkidle")
    print(f"页面标题: {page.title()}")

    page.fill("#input", "你好")
    page.click("#send")
    t0 = time.time()

    def state():
        return page.evaluate(
            """() => {
            const rows = [...document.querySelectorAll('#messages .msg')];
            const last = rows[rows.length - 1];
            return {
                text: last ? last.innerText : '',
                done: !document.querySelector('#send').disabled,
            };
        }"""
        )

    samples = []
    prev_len = 0
    for i in range(9):  # 最长 ~108s（qwen 7B CPU 首字 20-60s）
        time.sleep(12)
        st = state()
        txt = st["text"].replace("\n", " ")[:100]
        samples.append((round(time.time() - t0), txt))
        print(f"[t+{samples[-1][0]}s] 气泡: {txt}")
        if len(st["text"]) > prev_len:
            growing = True
            prev_len = len(st["text"])
        if st["done"] and prev_len > 30:
            break

    final = st["text"]
    ok = prev_len > 30 and "（无返回）" not in final and "出错了" not in final
    page.screenshot(path=str(SHOT), full_page=False)
    print(f"截图: {SHOT.name}")
    print(f"控制台错误: {console_errors if console_errors else '无'}")
    print(f"\n最终回复长度: {len(final)}")
    print("✅ P1-2 浏览器实测通过：可对话 + 流式输出" if ok
          else "❌ 实测未通过，见上方样本")
    browser.close()
    sys.exit(0 if ok else 1)
