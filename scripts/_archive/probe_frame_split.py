"""诊断：页面内 fetch → text → 用与 index.html 相同的解析算法处理，输出帧结构。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

JS = """
async () => {
  const resp = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: '你好', thread_id: null }),
  });
  const text = await resp.text();
  const frames = text.split('\\n\\n');
  const parsed = frames.slice(0, 4).map(f => {
    let ev = 'message', data = '', hasData = false;
    for (const line of f.split('\\n')) {
      if (line.startsWith('event:')) ev = line.slice(6).trim();
      else if (line.startsWith('data:')) { data += line.slice(5).trim(); hasData = true; }
    }
    return { ev, data: data.slice(0, 50), hasData };
  });
  return JSON.stringify({
    bytes: text.length,
    hasCR: text.includes('\\r'),
    frameCount: frames.length,
    parsed,
    rawHead: JSON.stringify(text.slice(0, 80)),
  });
}
"""

with sync_playwright() as pw:
    for p in BROWSERS:
        if Path(p).exists():
            browser = pw.chromium.launch(executable_path=p, headless=True)
            break
    page = browser.new_page()
    page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
    print(json.dumps(json.loads(page.evaluate(JS)), ensure_ascii=False, indent=1))
    browser.close()
