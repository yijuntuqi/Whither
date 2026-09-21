"""诊断探针：真实页面内 fetch('/chat') 读取原始 SSE 字节流（Playwright + Edge）。
判断：字节流到底有没有到达页面、何时终止、异常是什么。
用法: E:\\conda_envs\\langchain\\python.exe scripts/probe_page_fetch.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from playwright.sync_api import sync_playwright

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

PROBE_JS = """
async () => {
  const t0 = Date.now();
  const out = [];
  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: '你好' }),
    });
    out.push([Date.now() - t0, 'status=' + resp.status,
              'ct=' + resp.headers.get('content-type')]);
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    for (let i = 0; i < 10; i++) {
      const { value, done } = await reader.read();
      if (done) { out.push([Date.now() - t0, 'DONE']); break; }
      out.push([Date.now() - t0, dec.decode(value, { stream: true })
                .replaceAll('\\n', '|').slice(0, 70)]);
    }
  } catch (e) {
    out.push([Date.now() - t0, 'EXCEPTION ' + e.name + ': ' + e.message]);
  }
  return JSON.stringify(out);
}
"""

with sync_playwright() as pw:
    browser = None
    for p in BROWSERS:
        if Path(p).exists():
            browser = pw.chromium.launch(executable_path=p, headless=True)
            break
    page = browser.new_page()
    page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
    result = page.evaluate(PROBE_JS)
    import json
    for row in json.loads(result):
        print(f"[{row[0]:>6}ms] {row[1]}")
    browser.close()
