"""用系统 Edge 浏览器测试 Playwright 连接（无需下载）"""
import sys

# 方法 1: 检查系统 Chrome/Edge
import subprocess
import os

edge_paths = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

found = []
for p in edge_paths:
    if os.path.exists(p):
        found.append(p)
        print(f"✅ 找到浏览器: {p}")

if not found:
    print("❌ 没找到 Chrome/Edge")
    sys.exit(1)

# 方法 2: 用 Playwright 连接 Edge
from playwright.sync_api import sync_playwright

print(f"\n🚀 用 Playwright 启动 Edge...")

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=found[0],  # 用系统浏览器
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]
    )
    
    page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
    
    # 测试访问马蜂窝
    print("测试访问马蜂窝...")
    page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=15000)
    print(f"  URL: {page.url}")
    print(f"  Title: {page.title()}")
    print(f"  有 probe.js?: {'probe.js' in page.content()}")
    print(f"  Content len: {len(page.content())}")
    
    # 测试自由行页面
    print("\n测试自由行页面...")
    page.goto("https://www.mafengwo.cn/gonglve/ziyouxing/", wait_until="domcontentloaded", timeout=15000)
    print(f"  URL: {page.url}")
    print(f"  Title: {page.title()}")
    print(f"  Content len: {len(page.content())}")
    
    # 检查是否绕过 probe.js
    html = page.content()
    if len(html) > 5000 and 'probe.js' not in html[:2000]:
        print(f"  ✅ 成功绕过 probe.js！页面正常加载")
    else:
        print(f"  ⚠️ 仍然被 probe.js 拦截")
    
    browser.close()

print("\n🎉 Playwright + Edge 可用！")
