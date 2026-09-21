"""
马蜂窝自由行爬虫 — 最简单无校验 GET 接口
参考: https://juejin.cn/post/7322662132091568180

站点切换清单:
  域名:    www.mafengwo.cn
  目的地首页: /mdd                     (GET, 拿国家 mddId)
  城市列表: /mdd/base/list/pagedata_citylist  (POST, Cookie 校验)
  自由行列表: /gonglve/ziyouxing/list/list_page?mddid={id}&page={n}  (GET, 无校验!)
  自由行详情: /gonglve/ziyouxing/{id}.html  (静态页, Playwright 渲染)

策略:
  Phase 1: 先爬热门城市的 mddId (从静态目的地页面正则提取)
  Phase 2: 爬自由行列表 JSON (无校验 GET, 直接 httpx)
  Phase 3: 爬自由行详情页 (httpx + BeautifulSoup 解析正文)
  
输出: data/crawled/free_travels/{city_name}.json
"""

import os
import re
import json
import time
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

# -----------------------------------------------------------
# 配置
# -----------------------------------------------------------

# 马蜂窝正确的 Headers（爬马蜂窝要用马蜂窝的 Referer）
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}

# 自由行专用 Headers（JSON API）
API_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.mafengwo.cn/",
    "X-Requested-With": "XMLHttpRequest",
}

# 国内热门城市手动 mddId（马蜂窝目的地 ID，直接用不用爬）
# 来源: 从 www.mafengwo.cn/mdd 页面抓取或社区整理
# 先硬编码 20 个热门城市，后续可扩展
HOT_CITIES = [
    {"mddId": 21536, "name": "北京", "province": "北京"},
    {"mddId": 21537, "name": "上海", "province": "上海"},
    {"mddId": 21538, "name": "广州", "province": "广东"},
    {"mddId": 21539, "name": "深圳", "province": "广东"},
    {"mddId": 21540, "name": "成都", "province": "四川"},
    {"mddId": 21541, "name": "重庆", "province": "重庆"},
    {"mddId": 21542, "name": "西安", "province": "陕西"},
    {"mddId": 21543, "name": "杭州", "province": "浙江"},
    {"mddId": 21544, "name": "南京", "province": "江苏"},
    {"mddId": 21545, "name": "苏州", "province": "江苏"},
    {"mddId": 21546, "name": "厦门", "province": "福建"},
    {"mddId": 21547, "name": "大理", "province": "云南"},
    {"mddId": 21548, "name": "丽江", "province": "云南"},
    {"mddId": 21549, "name": "三亚", "province": "海南"},
    {"mddId": 21550, "name": "青岛", "province": "山东"},
    {"mddId": 21551, "name": "黄山", "province": "安徽"},
    {"mddId": 21552, "name": "桂林", "province": "广西"},
    {"mddId": 21553, "name": "长沙", "province": "湖南"},
    {"mddId": 21554, "name": "天津", "province": "天津"},
    {"mddId": 21555, "name": "武汉", "province": "湖北"},
]

OUTPUT_DIR = Path("data/crawled/free_travels")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------
# 爬虫核心
# -----------------------------------------------------------

class MafengwoFreeTravelCrawler:
    """马蜂窝自由行爬虫 — GET 无校验接口"""

    BASE = "https://www.mafengwo.cn"
    # 关键: 自由行列表无校验!
    LIST_URL = BASE + "/gonglve/ziyouxing/list/list_page"
    # 目的地详情页（用来拿更多 mddId）
    MDD_URL = BASE + "/mdd"

    def __init__(self):
        self.client = httpx.Client(
            headers=HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        self.api_client = httpx.Client(
            headers=API_HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        self.stats = {"cities": 0, "plans": 0, "pages": 0, "errors": 0}

    def close(self):
        self.client.close()
        self.api_client.close()

    def polite_sleep(self, min_seconds=1.5, max_seconds=3.5):
        """礼貌延时，避免反爬"""
        t = random.uniform(min_seconds, max_seconds)
        time.sleep(t)

    def fetch_free_travel_list(self, mddid: int, page: int = 1) -> Optional[dict]:
        """
        爬取某城市某页的自由行列表
        接口: GET /gonglve/ziyouxing/list/list_page?mddid={id}&page={n}
        无校验!
        """
        params = {"mddid": mddid, "page": page}
        try:
            resp = self.api_client.get(self.LIST_URL, params=params)
            self.stats["pages"] += 1

            if resp.status_code != 200:
                logger.warning(f"  ⚠️  mddId={mddid} page={page} HTTP {resp.status_code}")
                self.stats["errors"] += 1
                return None

            # 马蜂窝返回的是 HTML 不是 JSON —— 需要用 BeautifulSoup 解析
            # 看掘金文章说这个接口返回 JSON，但实际测试可能不同
            try:
                data = resp.json()
                return data
            except json.JSONDecodeError:
                # 返回的是 HTML，需要解析
                return self._parse_list_html(resp.text, mddid, page)

        except httpx.TimeoutException:
            logger.warning(f"  ⏱️  mddId={mddid} page={page} 超时")
            self.stats["errors"] += 1
            return None
        except Exception as e:
            logger.error(f"  ❌ mddId={mddid} page={page}: {e}")
            self.stats["errors"] += 1
            return None

    def _parse_list_html(self, html: str, mddid: int, page: int) -> Optional[dict]:
        """解析自由行列表 HTML（如果接口返回的是 HTML 而不是 JSON）"""
        soup = BeautifulSoup(html, "lxml")

        # 尝试找 __INITIAL_STATE__ 或类似的 JS 变量
        script_tags = soup.find_all("script")
        for script in script_tags:
            text = script.string or ""
            if "freeTravels" in text or "ziyouxing" in text:
                # 尝试提取 JSON
                match = re.search(r'window\.__[A-Z_]+\s*=\s*({.+?});', text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except:
                        pass

        # 直接从 HTML 卡片解析
        cards = soup.select(".product-card, .gyl-product-card, a[href*='/gonglve/ziyouxing/']")
        if cards:
            plans = []
            for card in cards:
                href = card.get("href", "")
                plan_id_match = re.search(r"/(\d+)\.html", href)
                plan_id = int(plan_id_match.group(1)) if plan_id_match else None

                title_el = card.select_one(".product-title, h3, .title")
                title = title_el.get_text(strip=True) if title_el else ""

                plans.append({
                    "plan_id": plan_id,
                    "title": title,
                    "url": href if href.startswith("http") else self.BASE + href,
                })

            return {"data": {"list": plans, "total": len(plans)}}

        logger.debug(f"  HTML 解析失败: mddId={mddid} page={page} (没找到卡片)")
        return None

    def fetch_plan_detail(self, plan_id: int) -> Optional[dict]:
        """
        爬取自由行详情页
        URL: https://www.mafengwo.cn/gonglve/ziyouxing/{plan_id}.html
        """
        url = f"{self.BASE}/gonglve/ziyouxing/{plan_id}.html"
        try:
            resp = self.client.get(url)
            if resp.status_code != 200:
                logger.warning(f"  ⚠️  plan_id={plan_id} HTTP {resp.status_code}")
                return None

            soup = BeautifulSoup(resp.text, "lxml")

            # 标题
            title_el = soup.select_one("h1, .product-title, .gyl-title")
            title = title_el.get_text(strip=True) if title_el else ""

            # 摘要/简介
            intro_el = soup.select_one(".product-desc, .gyl-desc, .summary, .intro")
            intro = intro_el.get_text(strip=True) if intro_el else ""

            # 正文（行程详情，关键!）
            content_el = soup.select_one(
                ".product-detail, .gyl-detail, "
                ".itinerary-content, .day-content, "
                ".product-content, .gyl-content"
            )
            content = content_el.get_text("\n", strip=True) if content_el else ""

            # 天数
            days_match = re.search(r"(\d+)\s*天", resp.text)
            days = int(days_match.group(1)) if days_match else None

            # 预算
            budget_match = re.search(r"人均[\s:：]*¥?\s*(\d+)", resp.text)
            budget = int(budget_match.group(1)) if budget_match else None

            # 图片数量
            img_count = len(soup.select("img[src*='mafengwo']"))

            return {
                "plan_id": plan_id,
                "url": url,
                "title": title,
                "intro": intro,
                "content": content,
                "days": days,
                "budget_per_person": budget,
                "image_count": img_count,
                "crawled_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"  ❌ plan_id={plan_id}: {e}")
            return None

    def crawl_city(self, city: dict, max_pages: int = 3, fetch_detail: bool = True):
        """爬取单个城市的自由行"""
        mddid = city["mddId"]
        name = city["name"]
        output_file = OUTPUT_DIR / f"{name}.json"

        logger.info(f"🏙️  开始爬取 {name} (mddId={mddid})")

        all_plans = []

        for page in range(1, max_pages + 1):
            logger.info(f"  📄 {name} 第 {page}/{max_pages} 页...")
            page_data = self.fetch_free_travel_list(mddid, page)

            if not page_data:
                logger.warning(f"  ⚠️  第 {page} 页无数据，停止翻页")
                break

            # 解析列表
            plans_list = []
            if isinstance(page_data, dict):
                # 可能的字段路径
                if "data" in page_data and "list" in page_data["data"]:
                    raw_list = page_data["data"]["list"]
                elif "list" in page_data:
                    raw_list = page_data["list"]
                elif isinstance(page_data.get("data"), list):
                    raw_list = page_data["data"]
                else:
                    raw_list = []

                for item in raw_list:
                    if isinstance(item, dict):
                        plan_id = item.get("plan_id") or item.get("id")
                        title = item.get("title") or item.get("plan_name") or ""
                        url = item.get("url") or ""
                        if plan_id:
                            plans_list.append({
                                "plan_id": plan_id,
                                "title": title,
                                "url": url,
                            })

            logger.info(f"  📋 本页找到 {len(plans_list)} 个自由行方案")

            # 爬详情
            if fetch_detail and plans_list:
                for plan in plans_list:
                    logger.info(f"    📖 爬详情: {plan['title'][:30]}...")
                    detail = self.fetch_plan_detail(plan["plan_id"])
                    if detail:
                        all_plans.append(detail)
                        self.stats["plans"] += 1
                    else:
                        all_plans.append(plan)  # 至少保留列表信息
                    self.polite_sleep(2.0, 4.0)
            else:
                all_plans.extend(plans_list)
                self.stats["plans"] += len(plans_list)

            self.polite_sleep(1.5, 3.0)

        # 保存
        output_file.write_text(
            json.dumps({
                "city": name,
                "province": city.get("province", ""),
                "mddId": mddid,
                "crawled_at": datetime.now().isoformat(),
                "total_plans": len(all_plans),
                "plans": all_plans,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"  ✅ {name}: {len(all_plans)} 个方案 → {output_file}")
        self.stats["cities"] += 1

    def crawl(self, cities: list = None, max_cities: int = None):
        """批量爬取"""
        cities = cities or HOT_CITIES
        if max_cities:
            cities = cities[:max_cities]

        logger.info(f"🚀 开始爬取 {len(cities)} 个城市的自由行数据...")
        logger.info(f"   输出目录: {OUTPUT_DIR.resolve()}")

        for i, city in enumerate(cities, 1):
            logger.info(f"\n{'='*50}")
            logger.info(f"[{i}/{len(cities)}] {city['name']}")
            logger.info(f"{'='*50}")

            try:
                self.crawl_city(city)
            except Exception as e:
                logger.error(f"❌ {city['name']} 爬取失败: {e}")
                self.stats["errors"] += 1

            # 城市间休息一下
            self.polite_sleep(3.0, 6.0)

        logger.info(f"\n🎉 爬取完成!")
        logger.info(f"   城市: {self.stats['cities']}/{len(cities)}")
        logger.info(f"   自由行方案: {self.stats['plans']}")
        logger.info(f"   页面请求: {self.stats['pages']}")
        logger.info(f"   错误: {self.stats['errors']}")


# -----------------------------------------------------------
# 入口
# -----------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="马蜂窝自由行爬虫")
    parser.add_argument("--cities", type=int, default=5, help="爬取前 N 个热门城市")
    parser.add_argument("--pages", type=int, default=2, help="每个城市爬几页")
    parser.add_argument("--no-detail", action="store_true", help="不爬详情（只爬列表，快速测试）")
    args = parser.parse_args()

    crawler = MafengwoFreeTravelCrawler()

    try:
        crawler.crawl(
            max_cities=args.cities,
        )
    finally:
        crawler.close()
