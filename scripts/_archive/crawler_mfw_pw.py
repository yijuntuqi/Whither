"""
马蜂窝自由行爬虫 (Playwright 版)
- 自动执行 probe.js + Cookie 校验
- 复用项目已安装的 Playwright（PDF 生成用的 Chromium）
- 输出: data/crawled/free_travels/{city}.json
"""
import re
import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup
from loguru import logger

# 热门城市 mddId
HOT_CITIES = [
    {"mddId": 21536, "name": "北京", "province": "北京"},
    {"mddId": 21537, "name": "上海", "province": "上海"},
    {"mddId": 21540, "name": "成都", "province": "四川"},
    {"mddId": 21542, "name": "西安", "province": "陕西"},
    {"mddId": 21543, "name": "杭州", "province": "浙江"},
    {"mddId": 21546, "name": "厦门", "province": "福建"},
    {"mddId": 21547, "name": "大理", "province": "云南"},
    {"mddId": 21549, "name": "三亚", "province": "海南"},
    {"mddId": 21541, "name": "重庆", "province": "重庆"},
    {"mddId": 21553, "name": "长沙", "province": "湖南"},
]

OUTPUT_DIR = Path("data/crawled/free_travels")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class MafengwoPlaywrightCrawler:
    """Playwright 无头浏览器爬虫 — 使用系统 Edge 绕过 probe.js"""

    BASE = "https://www.mafengwo.cn"
    
    # 自动寻找系统浏览器
    EDGE_PATHS = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.stats = {"cities": 0, "plans": 0, "errors": 0}
        
        # 找 Edge
        from pathlib import Path as P
        self.browser_exe = None
        for p in self.EDGE_PATHS:
            if P(p).exists():
                self.browser_exe = p
                break

    def start(self):
        self.playwright = sync_playwright().start()
        
        launch_kwargs = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        }
        if self.browser_exe:
            launch_kwargs["executable_path"] = self.browser_exe
            logger.info(f"🎯 使用系统浏览器: {self.browser_exe}")
        
        self.browser = self.playwright.chromium.launch(**launch_kwargs)
        
        # 预热马蜂窝（让 probe.js 执行 + 建立 cookies）
        self._warm_up()
        logger.info("🚀 Playwright 浏览器已启动 + 预热完成")

    def _warm_up(self):
        """预热：先访问一次马蜂窝让 probe.js 和 cookies 生效"""
        page = self.new_page()
        try:
            page.goto(self.BASE, wait_until="domcontentloaded", timeout=20000)
            import time; time.sleep(3)  # 等 probe.js
            # 再访问一次确认 probe 已过
            page.goto(self.BASE, wait_until="networkidle", timeout=20000)
            time.sleep(2)
            html = page.content()
            if "probe.js" in html[:2000]:
                logger.warning("  ⚠️ 预热后仍有 probe.js")
            else:
                logger.info("  ✅ 预热完成，probe.js 已绕过")
        except Exception as e:
            logger.warning(f"  ⚠️ 预热异常: {e}")
        finally:
            page.close()

    def stop(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("👋 浏览器已关闭")

    def new_page(self) -> Page:
        context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        # 绕过 webdriver 检测
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = context.new_page()
        return page

    def polite_sleep(self, min_s=1.5, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    def crawl_city_plans(self, city: dict, max_plans: int = 10) -> list:
        """
        爬取某城市的自由行方案列表
        用 Playwright 访问动态页面
        """
        mddid = city["mddId"]
        name = city["name"]
        url = f"{self.BASE}/gonglve/ziyouxing/list/list_page?mddid={mddid}&page=1"

        page = self.new_page()
        plans = []

        try:
            logger.info(f"  📄 访问: {url}")
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 等 probe.js 执行完（页面应该从 202 变成正常内容）
            time.sleep(3)

            # 尝试从 __INITIAL_STATE__ 或 __NUXT__ 提取 JSON
            state_data = page.evaluate("""() => {
                if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                if (window.__NUXT__) return JSON.stringify(window.__NUXT__);
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const t = s.textContent;
                    if (t.includes('freeTravels') || t.includes('ziyouxing')) {
                        return t.substring(0, 50000);
                    }
                }
                return null;
            }""")

            if state_data:
                try:
                    json_data = json.loads(state_data) if state_data.startswith("{") else None
                    if json_data:
                        logger.info(f"  💡 从 __INITIAL_STATE__ 提取到 JSON")
                        plans.extend(self._extract_plans_from_json(json_data))
                except json.JSONDecodeError:
                    pass

            # 从 HTML DOM 解析
            html = page.content()
            plans.extend(self._extract_plans_from_html(html, mddid))

            # 去重
            seen_ids = set()
            unique_plans = []
            for p in plans:
                pid = p.get("plan_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    unique_plans.append(p)
                elif not pid and p.get("title"):
                    unique_plans.append(p)

            logger.info(f"  ✅ {name}: {len(unique_plans)} 个方案")
            return unique_plans[:max_plans]

        except Exception as e:
            logger.error(f"  ❌ {name} 列表爬取失败: {e}")
            self.stats["errors"] += 1
            return []
        finally:
            page.close()

    def _extract_plans_from_json(self, data: dict) -> list:
        """从 INITIAL_STATE JSON 里找自由行列表"""
        plans = []
        text = json.dumps(data, ensure_ascii=False)
        
        # 搜索模式: 有 plan_id 或 有 ziyouxing 关键词的对象
        import re
        
        # 找所有 "id": 数字 且附近有 "title" 的
        # 简单方法: 递归查找有 title 字段且 plan_id/id 字段的对象
        def find_plans(obj, depth=0):
            if depth > 8 or obj is None:
                return
            if isinstance(obj, dict):
                has_title = any(k in obj for k in ("title", "plan_name", "name"))
                has_id = any(k in obj for k in ("plan_id", "id"))
                if has_title and has_id:
                    title = obj.get("title") or obj.get("plan_name") or obj.get("name", "")
                    pid = obj.get("plan_id") or obj.get("id")
                    if title and pid and isinstance(pid, (int, str)) and str(pid).isdigit():
                        plans.append({
                            "plan_id": int(pid),
                            "title": str(title)[:200],
                            "url": f"{self.BASE}/gonglve/ziyouxing/{pid}.html",
                        })
                for v in obj.values():
                    find_plans(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    find_plans(item, depth + 1)

        find_plans(data)
        return plans

    def _extract_plans_from_html(self, html: str, mddid: int) -> list:
        """从 HTML DOM 解析"""
        soup = BeautifulSoup(html, "lxml")
        plans = []

        # 找自由行卡片链接
        links = soup.select("a[href*='/gonglve/ziyouxing/']")
        for link in links:
            href = link.get("href", "")
            match = re.search(r"/(\d+)\.html", href)
            if match:
                pid = int(match.group(1))
                title = link.get_text(strip=True)[:100]
                if title and len(title) > 3:
                    plans.append({
                        "plan_id": pid,
                        "title": title,
                        "url": href if href.startswith("http") else self.BASE + href,
                    })

        # 找 data-plan-id 属性
        cards = soup.select("[data-plan-id], [data-product-id]")
        for card in cards:
            pid = card.get("data-plan-id") or card.get("data-product-id")
            if pid and str(pid).isdigit():
                title_el = card.select_one(".title, .product-title, h3")
                title = title_el.get_text(strip=True) if title_el else ""
                plans.append({
                    "plan_id": int(pid),
                    "title": title,
                    "url": f"{self.BASE}/gonglve/ziyouxing/{pid}.html",
                })

        return plans

    def crawl_plan_detail(self, plan_id: int) -> Optional[dict]:
        """爬取自由行详情页"""
        url = f"{self.BASE}/gonglve/ziyouxing/{plan_id}.html"
        page = self.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # 从 __INITIAL_STATE__ 提取详情 JSON
            detail_json = page.evaluate("""() => {
                if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                return null;
            }""")

            title, intro, content, days, budget = "", "", "", None, None

            if detail_json:
                try:
                    data = json.loads(detail_json)
                    # 递归找详情字段
                    def find_detail(obj, depth=0):
                        if depth > 10 or not isinstance(obj, (dict, list)):
                            return
                        if isinstance(obj, dict):
                            nonlocal title, intro, content, days, budget
                            if not title and obj.get("title"):
                                title = str(obj["title"])
                            if not intro and obj.get("summary"):
                                intro = str(obj["summary"])
                            if not content and obj.get("content"):
                                content = str(obj["content"])[:50000]
                            if not days and obj.get("days"):
                                try: days = int(obj["days"])
                                except: pass
                            if not budget and obj.get("budget"):
                                try: budget = int(obj["budget"])
                                except: pass
                            for v in obj.values():
                                find_detail(v, depth+1)
                        else:
                            for v in obj:
                                find_detail(v, depth+1)
                    find_detail(data)
                except:
                    pass

            # DOM 兜底
            if not content:
                html = page.content()
                soup = BeautifulSoup(html, "lxml")
                
                if not title:
                    t = soup.select_one("h1, .product-title, .gyl-title")
                    title = t.get_text(strip=True) if t else ""
                if not intro:
                    i = soup.select_one(".product-desc, .gyl-desc, .summary")
                    intro = i.get_text(strip=True) if i else ""
                if not content:
                    c = soup.select_one(".product-detail, .gyl-detail, .product-content")
                    content = c.get_text("\n", strip=True) if c else ""

            return {
                "plan_id": plan_id,
                "url": url,
                "title": title[:200],
                "intro": intro[:1000],
                "content": content[:50000],
                "days": days,
                "budget_per_person": budget,
                "crawled_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.warning(f"  ⚠️  plan_id={plan_id} 详情爬取失败: {e}")
            return None
        finally:
            page.close()

    def crawl_city(self, city: dict, max_plans: int = 8, fetch_detail: bool = True):
        """爬取单个城市"""
        logger.info(f"\n🏙️  {city['name']} (mddId={city['mddId']})")

        plans = self.crawl_city_plans(city, max_plans=max_plans)

        if fetch_detail and plans:
            detailed = []
            for i, plan in enumerate(plans):
                logger.info(f"  📖 [{i+1}/{len(plans)}] {plan.get('title', plan['plan_id'])}")
                detail = self.crawl_plan_detail(plan["plan_id"])
                if detail:
                    detailed.append(detail)
                    self.stats["plans"] += 1
                else:
                    detailed.append(plan)
                self.polite_sleep(2.0, 4.0)
            plans = detailed

        # 保存
        output = OUTPUT_DIR / f"{city['name']}.json"
        output.write_text(
            json.dumps({
                "city": city["name"],
                "province": city.get("province", ""),
                "mddId": city["mddId"],
                "crawled_at": datetime.now().isoformat(),
                "total_plans": len(plans),
                "plans": plans,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"  💾 {city['name']}: {len(plans)} 个方案 → {output}")
        self.stats["cities"] += 1

    def run(self, cities: list = None, max_cities: int = None):
        cities = cities or HOT_CITIES
        if max_cities:
            cities = cities[:max_cities]

        logger.info(f"🚀 开始爬取 {len(cities)} 个城市的自由行数据")
        logger.info(f"   输出目录: {OUTPUT_DIR.resolve()}")

        self.start()
        try:
            for i, city in enumerate(cities, 1):
                logger.info(f"\n{'='*50}")
                logger.info(f"[{i}/{len(cities)}] {city['name']}")
                logger.info(f"{'='*50}")
                try:
                    self.crawl_city(city)
                except Exception as e:
                    logger.error(f"❌ {city['name']}: {e}")
                    self.stats["errors"] += 1
                self.polite_sleep(3.0, 6.0)
        finally:
            self.stop()

        logger.info(f"\n🎉 完成!")
        logger.info(f"   城市: {self.stats['cities']}")
        logger.info(f"   方案: {self.stats['plans']}")
        logger.info(f"   错误: {self.stats['errors']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="马蜂窝自由行爬虫 (Playwright)")
    parser.add_argument("--cities", type=int, default=3, help="爬几个城市")
    parser.add_argument("--plans", type=int, default=6, help="每城市爬几个方案")
    parser.add_argument("--no-detail", action="store_true", help="不爬详情")
    parser.add_argument("--head", action="store_true", help="显示浏览器（非 headless）")
    args = parser.parse_args()

    crawler = MafengwoPlaywrightCrawler(headless=not args.head)
    crawler.run(max_cities=args.cities)
