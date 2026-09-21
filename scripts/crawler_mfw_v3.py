"""
马蜂窝自由行爬虫 V3 — 最优方案
架构: Playwright 一次预热拿 Cookie → httpx 批量 GET 接口 → JSON.html → BeautifulSoup

数据源:
  1. 城市列表: /mdd/base/list/pagedata_citylist (POST, 可能需要 cookie)
  2. 自由行列表: /gonglve/ziyouxing/list/list_page (GET, 有 cookie 就返回 JSON)
  3. 自由行详情: /gonglve/ziyouxing/{id}.html (静态页, httpx + cookie 应该能拿)

输出: data/crawled/free_travels/{city_name}.json
"""
import re
import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

# -----------------------------------------------------------
# 配置
# -----------------------------------------------------------

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"

BASE_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.mafengwo.cn/",
    "User-Agent": UA,
    "X-Requested-With": "XMLHttpRequest",
}

OUTPUT_DIR = Path("data/crawled/free_travels")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------
# Cookie 获取器（Playwright 一次预热）
# -----------------------------------------------------------

def get_mfw_cookies() -> dict:
    """用 Playwright 预热马蜂窝，拿 cookies"""
    from playwright.sync_api import sync_playwright
    from pathlib import Path as P
    
    # 找 Edge
    edge_exe = None
    for p in EDGE_PATHS:
        if P(p).exists():
            edge_exe = p
            break
    
    if not edge_exe:
        raise RuntimeError("没找到 Edge/Chrome 浏览器")
    
    logger.info(f"🔑 启动 Playwright 预热拿 Cookie...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=edge_exe,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1920, "height": 1080},
        )
        ctx.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined});""")
        page = ctx.new_page()
        
        # 两次访问让 probe.js 跑 + cookie 生效
        page.goto("https://www.mafengwo.cn/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        page.goto("https://www.mafengwo.cn/", wait_until="networkidle", timeout=20000)
        time.sleep(2)
        
        cookies = ctx.cookies()
        browser.close()
    
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    logger.info(f"✅ 拿到 {len(cookies)} 个 cookies")
    return cookie_header


# -----------------------------------------------------------
# 城市列表爬取
# -----------------------------------------------------------

def fetch_city_list(cookie: str) -> list:
    """
    爬取国内热门城市列表（从马蜂窝目的地页面）
    返回: [{mddId, name, province}, ...]
    """
    headers = {**BASE_HEADERS, "Cookie": cookie, "Referer": "https://www.mafengwo.cn/mdd"}
    client = httpx.Client(headers=headers, follow_redirects=True, timeout=15.0)
    
    cities = []
    
    # 方法 1: 先试 POST 接口（掘金文章提到的）
    url = "https://www.mafengwo.cn/mdd/base/list/pagedata_citylist"
    payload = {"mddid": 1, "page": 1}  # mddid=1 是中国
    
    try:
        resp = client.post(url, data=payload)
        if resp.status_code == 200 and "probe.js" not in resp.text[:500]:
            try:
                data = resp.json()
                # 解析...
                logger.info(f"POST 接口返回: ret={data.get('ret')}")
            except:
                pass
    except Exception as e:
        logger.debug(f"POST 失败: {e}")
    
    # 方法 2: 从目的地首页 HTML 里提取
    resp = client.get("https://www.mafengwo.cn/mdd")
    if resp.status_code == 200 and "probe.js" not in resp.text[:500]:
        soup = BeautifulSoup(resp.text, "lxml")
        
        # 找城市链接
        for a in soup.select("a[href*='/mdd/citylist/']"):
            href = a.get("href", "")
            m = re.search(r"citylist/(\d+)", href)
            if m:
                mdd_id = int(m.group(1))
                name = a.get_text(strip=True)
                if name and len(name) <= 10:
                    cities.append({"mddId": mdd_id, "name": name})
    
    client.close()
    
    if cities:
        # 去重
        seen = set()
        unique = []
        for c in cities:
            if c["mddId"] not in seen:
                seen.add(c["mddId"])
                unique.append(c)
        logger.info(f"✅ 从目的地页面拿到 {len(unique)} 个城市")
        return unique
    
    # 方法 3: 硬编码（兜底）
    logger.warning("⚠️  没爬到城市列表，用硬编码热门城市")
    return [
        {"mddId": 21536, "name": "北京", "province": "北京"},
        {"mddId": 21537, "name": "上海", "province": "上海"},
        {"mddId": 21540, "name": "成都", "province": "四川"},
        {"mddId": 21542, "name": "西安", "province": "陕西"},
        {"mddId": 21543, "name": "杭州", "province": "浙江"},
        {"mddId": 21546, "name": "厦门", "province": "福建"},
        {"mddId": 21549, "name": "三亚", "province": "海南"},
        {"mddId": 21541, "name": "重庆", "province": "重庆"},
        {"mddId": 21547, "name": "大理", "province": "云南"},
        {"mddId": 21553, "name": "长沙", "province": "湖南"},
    ]


# -----------------------------------------------------------
# 自由行列表爬取
# -----------------------------------------------------------

def fetch_free_travel_list(cookie: str, mddid: int, page: int = 1) -> Optional[dict]:
    """爬取某城市某页的自由行列表 — 返回解析后的方案列表"""
    headers = {**BASE_HEADERS, "Cookie": cookie}
    url = f"https://www.mafengwo.cn/gonglve/ziyouxing/list/list_page"
    params = {"mddid": mddid, "page": page}
    
    client = httpx.Client(headers=headers, timeout=20.0)
    try:
        resp = client.get(url, params=params)
        
        if resp.status_code != 200:
            logger.debug(f"  HTTP {resp.status_code}")
            return None
        
        if "probe.js" in resp.text[:500]:
            logger.warning(f"  Cookie 失效或被反爬")
            return None
        
        # 解析 JSON: {"ret":1,"html":"..."}
        data = resp.json()
        if data.get("ret") != 1:
            logger.debug(f"  ret != 1: {data.get('ret')}")
            return None
        
        html_content = data.get("html", "")
        soup = BeautifulSoup(html_content, "lxml")
        
        plans = []
        for item in soup.select(".item.clearfix"):
            link = item.select_one("a")
            if not link:
                continue
            
            href = link.get("href", "")
            pid_match = re.search(r"/(\d+)\.html", href)
            if not pid_match:
                continue
            
            plan_id = int(pid_match.group(1))
            title_el = item.select_one("h3")
            loc_el = item.select_one(".location")
            view_el = item.select_one(".view")
            li_els = item.select("li")
            
            plans.append({
                "plan_id": plan_id,
                "title": title_el.get_text(strip=True) if title_el else "",
                "url": f"https://www.mafengwo.cn{href}",
                "highlights": [li.get_text(strip=True) for li in li_els],
                "location": loc_el.get_text(strip=True) if loc_el else "",
                "views": view_el.get_text(strip=True) if view_el else "",
            })
        
        # 分页信息
        count_el = soup.select_one(".count")
        pagination = count_el.get_text(strip=True) if count_el else ""
        
        return {"plans": plans, "pagination": pagination}
        
    except httpx.TimeoutException:
        logger.debug(f"  超时")
        return None
    except Exception as e:
        logger.debug(f"  解析异常: {e}")
        return None
    finally:
        client.close()


def fetch_free_travel_detail(cookie: str, plan_id: int) -> Optional[dict]:
    """爬取自由行详情页"""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.mafengwo.cn/",
        "User-Agent": UA,
        "Cookie": cookie,
    }
    url = f"https://www.mafengwo.cn/gonglve/ziyouxing/{plan_id}.html"
    
    client = httpx.Client(headers=headers, timeout=20.0, follow_redirects=True)
    try:
        resp = client.get(url)
        
        if resp.status_code != 200 or "probe.js" in resp.text[:500]:
            return None
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        title_el = soup.select_one("h1, .product-title, .gyl-title")
        intro_el = soup.select_one(".product-desc, .gyl-desc, .summary")
        content_el = soup.select_one(
            ".product-detail, .gyl-detail, .itinerary-content, .product-content"
        )
        
        content = ""
        if content_el:
            # 用标题分段
            for section in content_el.select(".day-title, .day-header, h3, h2, .day"):
                content += f"\n## {section.get_text(strip=True)}\n"
                next_el = section.find_next_sibling()
                while next_el and next_el.name not in ("h2", "h3", "div"):
                    next_el = next_el.find_next_sibling()
            if not content:
                content = content_el.get_text("\n", strip=True)
        
        if not content:
            content = intro_el.get_text("\n", strip=True) if intro_el else ""
        
        # 元数据
        text_all = resp.text
        days_match = re.search(r"(\d+)\s*天", text_all)
        budget_match = re.search(r"人均[\s:：]*¥?\s*(\d+)", text_all)
        
        return {
            "plan_id": plan_id,
            "url": url,
            "title": title_el.get_text(strip=True) if title_el else "",
            "intro": intro_el.get_text(strip=True) if intro_el else "",
            "content": content[:30000],
            "days": int(days_match.group(1)) if days_match else None,
            "budget_per_person": int(budget_match.group(1)) if budget_match else None,
            "crawled_at": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.debug(f"  详情异常 plan_id={plan_id}: {e}")
        return None
    finally:
        client.close()


# -----------------------------------------------------------
# 主爬虫类
# -----------------------------------------------------------

class MafengwoCrawler:
    def __init__(self, max_cities: int = 10, max_pages_per_city: int = 3, fetch_detail: bool = True):
        self.max_cities = max_cities
        self.max_pages_per_city = max_pages_per_city
        self.fetch_detail = fetch_detail
        self.cookie = None
        self.stats = {"cities": 0, "plans_list": 0, "plans_detail": 0, "errors": 0}

    def run(self):
        logger.info("🚀 马蜂窝自由行爬虫 V3 (httpx + Playwright 预热)")
        logger.info(f"   目标: {self.max_cities} 城市, 每城市 {self.max_pages_per_city} 页")
        
        # Step 1: 拿 Cookie
        self.cookie = get_mfw_cookies()
        
        # Step 2: 拿城市列表
        cities = fetch_city_list(self.cookie)
        cities = cities[:self.max_cities]
        logger.info(f"📍 目标城市: {[c['name'] for c in cities]}")
        
        # Step 3: 逐城市爬取
        for i, city in enumerate(cities, 1):
            logger.info(f"\n{'='*50}")
            logger.info(f"[{i}/{len(cities)}] {city['name']} (mddId={city['mddId']})")
            logger.info(f"{'='*50}")
            
            self.crawl_city(city)
            time.sleep(random.uniform(2, 4))
        
        # Step 4: 汇总
        logger.info(f"\n🎉 爬取完成!")
        logger.info(f"   城市: {self.stats['cities']}")
        logger.info(f"   方案数(列表): {self.stats['plans_list']}")
        logger.info(f"   方案数(详情): {self.stats['plans_detail']}")
        logger.info(f"   错误: {self.stats['errors']}")
        logger.info(f"\n📁 数据目录: {OUTPUT_DIR.resolve()}")
        
        # 列出生成的文件
        files = list(OUTPUT_DIR.glob("*.json"))
        for f in files:
            size_kb = f.stat().st_size / 1024
            logger.info(f"   {f.name} ({size_kb:.1f} KB)")
    
    def crawl_city(self, city: dict):
        mddid = city["mddId"]
        name = city["name"]
        
        all_plans = []
        
        for page in range(1, self.max_pages_per_city + 1):
            logger.info(f"  📄 第 {page}/{self.max_pages_per_city} 页...")
            result = fetch_free_travel_list(self.cookie, mddid, page)
            
            if not result or not result["plans"]:
                logger.info(f"  本页无数据，停止翻页")
                break
            
            plans = result["plans"]
            logger.info(f"  📋 本页 {len(plans)} 条方案")
            
            if self.fetch_detail:
                for j, plan in enumerate(plans):
                    logger.info(f"    📖 [{j+1}/{len(plans)}] {plan['title'][:30]}...")
                    detail = fetch_free_travel_detail(self.cookie, plan["plan_id"])
                    if detail:
                        all_plans.append(detail)
                        self.stats["plans_detail"] += 1
                    else:
                        all_plans.append(plan)  # 至少保留列表信息
                    time.sleep(random.uniform(1.5, 3.0))
            else:
                all_plans.extend(plans)
                self.stats["plans_detail"] += len(plans)
            
            self.stats["plans_list"] += len(plans)
            time.sleep(random.uniform(1, 2))
        
        if all_plans:
            output = OUTPUT_DIR / f"{name}.json"
            output.write_text(
                json.dumps({
                    "city": name,
                    "mddId": mddid,
                    "crawled_at": datetime.now().isoformat(),
                    "total_plans": len(all_plans),
                    "plans": all_plans,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info(f"  💾 {name}: {len(all_plans)} 方案 → {output}")
            self.stats["cities"] += 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="马蜂窝自由行爬虫 V3")
    parser.add_argument("--cities", type=int, default=3, help="爬几个城市")
    parser.add_argument("--pages", type=int, default=2, help="每城市几页")
    parser.add_argument("--no-detail", action="store_true", help="不爬详情（快速测试）")
    args = parser.parse_args()
    
    crawler = MafengwoCrawler(
        max_cities=args.cities,
        max_pages_per_city=args.pages,
        fetch_detail=not args.no_detail,
    )
    crawler.run()
