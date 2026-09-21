"""
马蜂窝自由行批量爬虫
- 从 city_index.json 读城市
- Playwright 预热拿 cookie → httpx 爬自由行列表（不爬详情）
- 支持断点续传（已爬城市跳过）、cookie 失效自动重新预热

输出: data/crawled/free_travels/{城市名}.json（与 vectorize.py 输入格式一致）

用法:
  python scripts/crawler_mfw_batch.py --group zhixiashi --pages 3
  python scripts/crawler_mfw_batch.py --group domestic --pages 3
"""
import sys, json, time, random
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path("scripts").resolve()))
from crawler_mfw_v3 import get_mfw_cookies, fetch_free_travel_list

CITY_INDEX = Path("data/crawled/city_index.json")
OUTPUT_DIR = Path("data/crawled/free_travels")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ZHIXIASHI = {"北京", "上海", "天津", "重庆"}


def load_cities(group: str) -> list[dict]:
    data = json.loads(CITY_INDEX.read_text(encoding="utf-8"))
    all_cities = data["all_cities"]

    if group == "zhixiashi":
        cities = [c for c in all_cities if c["province"] in ZHIXIASHI and c["region"] == "domestic"]
    elif group == "domestic":
        cities = [c for c in all_cities if c["region"] == "domestic"]
    else:
        raise ValueError(f"未知 group: {group}")
    return cities


def already_crawled(city_name: str) -> bool:
    f = OUTPUT_DIR / f"{city_name}.json"
    if not f.exists():
        return False
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d.get("total_plans", 0) > 0
    except Exception:
        return False


def crawl_one_city(cookie: str, city: dict, pages: int) -> tuple[list, str]:
    """爬单个城市，返回 (plans, cookie)。cookie 失效时刷新。"""
    all_plans = []
    for page in range(1, pages + 1):
        result = fetch_free_travel_list(cookie, city["id"], page)

        # cookie 失效：重新预热后重试一次
        if result is None:
            logger.warning(f"    第{page}页失败，重新预热 cookie...")
            cookie = get_mfw_cookies()
            result = fetch_free_travel_list(cookie, city["id"], page)
            if result is None:
                logger.warning(f"    第{page}页仍失败，停止该城市翻页")
                break

        plans = result["plans"]
        if not plans:
            logger.info(f"    第{page}页无数据，停止翻页")
            break

        all_plans.extend(plans)
        logger.info(f"    第{page}/{pages}页: +{len(plans)} (累计 {len(all_plans)})")
        if page < pages:
            time.sleep(random.uniform(0.8, 1.6))

    return all_plans, cookie


def save_city(city: dict, plans: list):
    output = {
        "city": city["name"],
        "mddId": city["id"],
        "province": city["province"],
        "crawled_at": datetime.now().isoformat(),
        "total_plans": len(plans),
        "plans": plans,
    }
    f = OUTPUT_DIR / f"{city['name']}.json"
    f.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="马蜂窝自由行批量爬虫")
    parser.add_argument("--group", default="zhixiashi", choices=["zhixiashi", "domestic"])
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--force", action="store_true", help="忽略断点续传，强制重爬")
    args = parser.parse_args()

    cities = load_cities(args.group)
    logger.info(f"🚀 批量爬虫 group={args.group}  城市数={len(cities)}  每城{args.pages}页")

    cookie = get_mfw_cookies()

    done, skipped, failed = 0, 0, 0
    for i, city in enumerate(cities, 1):
        logger.info(f"\n[{i}/{len(cities)}] {city['name']} (id={city['id']}, {city['province']})")

        if not args.force and already_crawled(city["name"]):
            logger.info("  ⏭️  已爬过，跳过（--force 可重爬）")
            skipped += 1
            continue

        plans, cookie = crawl_one_city(cookie, city, args.pages)

        if plans:
            save_city(city, plans)
            logger.info(f"  💾 保存 {len(plans)} 条 → {OUTPUT_DIR / (city['name'] + '.json')}")
            done += 1
        else:
            logger.warning(f"  ❌ 该城市无数据")
            failed += 1

        time.sleep(random.uniform(1.5, 3.0))

    logger.info(f"\n🎉 完成 group={args.group}")
    logger.info(f"   本次爬取: {done}  跳过: {skipped}  失败: {failed}")
    logger.info(f"   数据目录: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
