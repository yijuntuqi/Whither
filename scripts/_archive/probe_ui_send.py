"""二分诊断：驱动页面真实 send()（按钮点击路径），采样气泡文本。
判断 UI JS 的 send() 是否正确解析并显示 error/token 事件。
用法: E:\\conda_envs\\langchain\\python.exe scripts/probe_ui_send.py
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

with sync_playwright() as pw:
    browser = None
    for p in BROWSERS:
        if Path(p).exists():
            browser = pw.chromium.launch(executable_path=p, headless=True)
            break
    page = browser.new_page()
    page.on("console", lambda m: print(f"  [console.{m.type}] {m.text[:100]}"))
    page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")

    # 直接驱动真实 send()：设置输入框 + 点击按钮
    page.evaluate(
        """() => {
        const i = document.querySelector('#input');
        i.value = '你好';
        document.querySelector('#send').click();
        return 'clicked';
    }"""
    )
    print("已点击发送")

    t0 = time.time()
    for _ in range(6):
        time.sleep(4)
        state = page.evaluate(
            """() => {
            const rows = [...document.querySelectorAll('#messages .msg')];
            const last = rows[rows.length - 1];
            return JSON.stringify({
                rows: rows.length,
                lastText: last ? last.innerText.replaceAll('\\n', ' ').slice(0, 120) : null,
                sendDisabled: document.querySelector('#send').disabled,
            });
        }"""
        )
        print(f"[t+{time.time()-t0:.0f}s] {json.loads(state)}")
    browser.close()
