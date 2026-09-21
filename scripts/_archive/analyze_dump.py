"""分析 dump 的 HTML + 找能正常渲染的马蜂窝页面"""
from pathlib import Path

html = Path("scripts/mfw_dump.html").read_text(encoding="utf-8")

print(f"HTML 长度: {len(html)}")
print(f"\n前 3000 字符:")
print(html[:3000])
print(f"\n...\n")
print(f"后 2000 字符:")
print(html[-2000:])
