"""
生成马蜂窝全量城市索引（地理校验版）

背景：mdd_home.html 中一个 dt 含多个省份、dd 内城市混排且无边界，
      DOM 解析归属会错位。这里直接用经过地理校验的「省/国家 → 城市ID」
      结构构建索引，城市名从 HTML 的 id→name 映射填充。

输出: data/crawled/city_index.json
"""
import re, json
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

SRC = Path("data/probe_city/mdd_home.html")
OUT = Path("data/crawled/city_index.json")
LINK_RE = re.compile(r"/travel-scenic-spot/mafengwo/(\d+)\.html")

# -----------------------------------------------------------
# 地理校验树：每项 (省/国家名, region, province_id, [城市ID...])
# region: domestic / gangaotai / abroad
# -----------------------------------------------------------
GEO_TREE = [
    # ===== 国内：直辖市 =====
    ("北京", "domestic", None, [10065]),
    ("上海", "domestic", None, [10099]),
    ("天津", "domestic", None, [10320]),
    ("重庆", "domestic", None, [10208]),
    # ===== 国内：省/自治区 =====
    ("云南", "domestic", 12711, [10186, 10487, 10807, 10482, 10121, 15950, 10809, 10018, 10651, 12141]),
    ("四川", "domestic", 12703, [10035, 10136, 10061, 10011, 10564, 10163, 10091, 11642, 10143, 17315]),
    ("浙江", "domestic", 14575, [10156, 10434, 10010, 10445, 11534, 10439, 10089]),
    ("海南", "domestic", 12938, [10030, 14786, 10513]),
    ("福建", "domestic", 12871, [10132, 12522, 10039, 11246]),
    ("江苏", "domestic", 14387, [10684, 10207, 10140, 10128, 11729, 10802, 10804, 10435]),
    ("广东", "domestic", 14674, [10088, 10198, 10269, 13063]),
    ("广西", "domestic", 12810, [10095, 10027, 10796, 11755, 10453, 18065]),
    ("西藏", "domestic", 12700, [10442, 10814, 10073]),
    ("贵州", "domestic", 14103, [10381, 11932, 14753, 14484, 10085]),
    ("陕西", "domestic", None, [10195]),
    ("青海", "domestic", 12788, [10799, 10800, 19603]),
    ("甘肃", "domestic", None, [10240, 10783, 10076, 11340, 11353]),
    ("新疆", "domestic", 13061, []),  # 13061 本身是省级目的地入口
    ("山东", "domestic", 12976, [10444, 10284, 10805, 10256, 11243, 11270, 10443]),
    ("山西", "domestic", None, [10547, 11241, 10057, 10087]),
    ("湖南", "domestic", 13732, [10267, 10024, 10792]),
    ("湖北", "domestic", None, [10133, 10521, 10489]),
    ("安徽", "domestic", 12719, [10440, 10825]),
    ("江西", "domestic", None, [10045, 10589, 10244, 11465, 11754]),
    ("河南", "domestic", None, [10449, 10094, 10632]),
    ("河北", "domestic", 14407, [10209, 11499, 10432, 11386]),
    ("内蒙古", "domestic", 12720, [10774, 10390, 10414]),
    ("黑龙江", "domestic", None, [10068, 10427, 10127]),
    ("辽宁", "domestic", None, [10301, 10584, 10728]),

    # ===== 港澳台 =====
    ("台湾", "gangaotai", 12684, [10819, 21434, 15325, 11065, 16405, 23039, 12594, 10044]),
    ("香港", "gangaotai", 10189, []),  # 10189 本身即城市目的地
    ("澳门", "gangaotai", 10206, []),

    # ===== 亚洲 =====
    ("日本", "abroad", 10183, [10222, 10765, 11042, 11041, 10746, 10768, 10769, 16283, 11043, 15297, 15298, 61629, 59480, 19816, 10766]),
    ("泰国", "abroad", 10083, [11047, 15284, 11045, 14210, 16980, 11046, 16209]),
    ("新加坡", "abroad", 10754, []),
    ("印度尼西亚", "abroad", None, [10460, 13752]),
    ("马来西亚", "abroad", 10097, [10760, 28411, 11049, 11051]),
    ("越南", "abroad", 10180, [16102, 16315, 16105, 16359, 11055, 11053]),
    ("柬埔寨", "abroad", 10070, [10406, 15308, 15305]),
    ("缅甸", "abroad", None, [16113, 16112, 16114]),
    ("菲律宾", "abroad", 10067, [10737, 29500, 16115, 16117]),
    ("文莱", "abroad", None, [10753]),
    ("马尔代夫", "abroad", 10101, [11068, 33109, 17748, 17751]),
    ("阿联酋", "abroad", 11213, [11214, 11215]),
    ("伊朗", "abroad", None, [47029, 49450, 49111]),
    ("斯里兰卡", "abroad", 11058, [11059, 11061, 11062, 63702]),
    ("尼泊尔", "abroad", 10069, [11275, 16126, 16127]),
    ("印度", "abroad", 10182, [16120, 16122, 18034, 16123, 16125]),

    # ===== 美洲 =====
    ("美国", "abroad", 10062, [10926, 10742, 10579, 10929, 10745, 10925, 10917, 10916, 10928, 11703, 10927, 10077, 19016]),
    ("加拿大", "abroad", 10177, []),
    ("巴西", "abroad", 10160, []),
    ("古巴", "abroad", None, [11684]),
    ("墨西哥", "abroad", None, [11656]),
    ("秘鲁", "abroad", None, [11005]),

    # ===== 欧洲 =====
    ("英国", "abroad", 10122, [11124, 11125, 14784, 16162, 11129]),
    ("爱尔兰", "abroad", None, [11132]),
    ("意大利", "abroad", 10051, [10063, 11083, 11087, 11084, 16428]),
    ("法国", "abroad", 10171, [10573, 11122]),
    ("瑞士", "abroad", None, [11109, 11110, 11112, 11108]),
    ("西班牙", "abroad", 10173, [10102, 11133, 11135, 11138, 21366]),
    ("葡萄牙", "abroad", 10172, [11142, 11171, 63452]),
    ("俄罗斯", "abroad", 10300, [11155, 14635, 15338, 13006]),
    ("德国", "abroad", 10176, [11081, 10958, 10755, 11080, 35987]),
    ("奥地利", "abroad", None, [11091, 18705, 11167]),
    ("希腊", "abroad", 10168, [16095, 11143]),
    ("土耳其", "abroad", None, [11228, 16876, 18041]),
    ("捷克", "abroad", 10174, [10761, 11141, 22351]),
    ("匈牙利", "abroad", None, [11095]),
    ("冰岛", "abroad", 14431, [16084, 62910, 62907, 105930]),
    ("荷兰", "abroad", 11099, [11100, 11101, 16099]),
    ("比利时", "abroad", None, [11106, 16100]),
    ("芬兰", "abroad", None, [10448]),
    ("挪威", "abroad", None, [11160]),
    ("丹麦", "abroad", None, [11157]),
    ("瑞典", "abroad", None, [10214]),
    ("塞尔维亚", "abroad", None, [26909]),
    ("克罗地亚", "abroad", None, [11853]),

    # ===== 大洋洲 =====
    ("澳大利亚", "abroad", 10202, [10855, 10856, 10858, 19036, 17339, 10857]),
    ("新西兰", "abroad", 10544, [10865, 10885, 15920]),
    ("斐济", "abroad", None, [11044]),
    ("大溪地", "abroad", None, [10344]),

    # ===== 非洲 =====
    ("埃及", "abroad", 10178, [11367, 11185, 51454, 48718, 16708]),
    ("摩洛哥", "abroad", 12033, [16077, 113734, 16078, 113733]),
    ("毛里求斯", "abroad", None, [11761]),
    ("塞舌尔", "abroad", None, [16827]),
    ("肯尼亚", "abroad", None, [10029]),
    ("马达加斯加", "abroad", None, [17439]),
]


def build_id_name_map() -> dict:
    soup = BeautifulSoup(SRC.read_text(encoding="utf-8"), "lxml")
    id_name = {}
    for a in soup.find_all("a", href=LINK_RE):
        cid = int(LINK_RE.search(a["href"]).group(1))
        name = a.get_text(strip=True)
        if name and cid not in id_name:
            id_name[cid] = name
    return id_name


def main():
    id_name = build_id_name_map()

    provinces = []
    flat = []
    missing = []
    all_leaf_ids = set()

    for pname, region, pid, city_ids in GEO_TREE:
        cities = []
        # 省级目的地自身若没有下属城市（如香港、新加坡），把 pid 作为叶子城市
        leaf_ids = list(city_ids)
        if not leaf_ids and pid is not None:
            leaf_ids = [pid]

        for cid in leaf_ids:
            cname = id_name.get(cid)
            if not cname:
                missing.append((cid, pname))
                cname = pname  # 兜底用省名
            cities.append({"id": cid, "name": cname})
            flat.append({"id": cid, "name": cname, "province": pname, "region": region})
            all_leaf_ids.add(cid)

        provinces.append({
            "province": pname,
            "province_id": pid,
            "region": region,
            "city_count": len(cities),
            "cities": cities,
        })

    n_dom = sum(1 for c in flat if c["region"] == "domestic")
    n_gat = sum(1 for c in flat if c["region"] == "gangaotai")
    n_abr = sum(1 for c in flat if c["region"] == "abroad")

    output = {
        "generated_at": datetime.now().isoformat(),
        "source": str(SRC),
        "total_cities": len(flat),
        "counts": {"domestic": n_dom, "gangaotai": n_gat, "abroad": n_abr},
        "provinces": provinces,
        "all_cities": flat,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 城市索引: {OUT}")
    print(f"   总城市: {len(flat)}  (国内 {n_dom} / 港澳台 {n_gat} / 国外 {n_abr})")
    print(f"   省/国家分组: {len(provinces)}")
    if missing:
        print(f"\n⚠️  以下 ID 在 HTML 没找到名字（用省名兜底）:")
        for cid, p in missing:
            print(f"    {cid}  ({p})")

    print(f"\n国内分组校验:")
    for p in provinces:
        if p["region"] != "domestic":
            continue
        names = "、".join(c["name"] for c in p["cities"])
        print(f"  {p['province']:4s}[{p['city_count']:2d}]: {names}")


if __name__ == "__main__":
    main()
