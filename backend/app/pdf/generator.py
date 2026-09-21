"""
PDF 生成器：itinerary dict → HTML → Playwright(Edge) → PDF
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"

# 系统浏览器常见安装路径（Windows/macOS/Linux）
_SYSTEM_BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def _resolve_browser() -> dict:
    """浏览器解析优先级：PLAYWRIGHT_EXECUTABLE_PATH 环境变量 → Playwright 自带
    Chromium（部署环境用 playwright install 安装）→ 系统已装的 Edge/Chrome。"""
    env_path = os.getenv("PLAYWRIGHT_EXECUTABLE_PATH")
    if env_path and Path(env_path).exists():
        return {"executable_path": env_path}
    return {}  # 先尝试 Playwright 自带 Chromium


def _launch_browser(pw):
    """按优先级启动 Chromium 内核浏览器，全部失败时抛出带指引的异常"""
    # 1) 环境变量指定的浏览器
    opts = _resolve_browser()
    if opts:
        return pw.chromium.launch(**opts, headless=True)
    # 2) Playwright 自带 Chromium（需要 playwright install chromium）
    try:
        return pw.chromium.launch(headless=True)
    except Exception:
        pass
    # 3) 系统浏览器探测
    for p in _SYSTEM_BROWSERS:
        if Path(p).exists():
            return pw.chromium.launch(executable_path=p, headless=True)
    raise RuntimeError(
        "未找到可用的 Chromium 内核浏览器。解决方案任选其一：\n"
        "  a) playwright install chromium（推荐，部署环境用）\n"
        "  b) 设置环境变量 PLAYWRIGHT_EXECUTABLE_PATH 指向 Edge/Chrome 的可执行文件"
    )

from backend.app.pdf.template import render_html


def _safe_name(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")
    return name[:40] or "itinerary"


def generate_pdf(data: dict, out_dir: Path = EXPORT_DIR) -> Path:
    """itinerary dict → PDF 文件路径（同步）"""
    out_dir.mkdir(parents=True, exist_ok=True)
    html_str = render_html(data)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = out_dir / f"{_safe_name(data.get('title', 'itinerary'))}_{stamp}.html"
    pdf_path = out_dir / f"{_safe_name(data.get('title', 'itinerary'))}_{stamp}.pdf"
    html_path.write_text(html_str, encoding="utf-8")

    from playwright.sync_api import sync_playwright
    t0 = time.time()
    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()
    logger.info(f"PDF 生成: {pdf_path.name} ({pdf_path.stat().st_size/1024:.0f} KB, {time.time()-t0:.1f}s)")
    return pdf_path
