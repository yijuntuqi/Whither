"""对生成的 HTML 截图，人工检查排版"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
html = sorted(Path("data/exports").glob("*.html"))[-1]
out = Path("data/exports/preview.png")

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=EDGE, headless=True)
    page = b.new_page(viewport={"width": 794, "height": 1123})  # A4 @96dpi
    page.goto(html.resolve().as_uri(), wait_until="networkidle")
    page.screenshot(path=str(out), full_page=True)
    b.close()
print(f"✅ 截图: {out.resolve()}")
