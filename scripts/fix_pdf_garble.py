"""
PDF 乱码根治 · 方案B3：语料 bigram 条件概率匹配（PDF 自举）

原理：错字源自嵌入字体缺 ToUnicode CMap，PDF 内映射一致、错字占比仅 ~6%，
      故可用「PDF 自身正常部分 + mafengwo_free 干净语料」的字级 bigram 做
      条件概率匹配：对错字每个上下文 (L, R)，
          score(t) = P(t|L) · P(t|R)
      取 argmax，top1/top2 比值为置信度。
错字筛选：PDF 频次 ≥10 且 jieba 词典与干净语料均未收录（非法现代汉字）。
自检：用户人工确认的 14 个映射为金标准，命中率作为 matcher 可信度证据。

用法:
  python scripts/fix_pdf_garble.py            # 推断 + 自检 → data/pdf_cid_map.json
  python scripts/fix_pdf_garble.py --apply    # 高置信映射写入 scripts/cid_fix_extra.py
"""
import sys, json, re, time
from collections import Counter, defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

from loguru import logger
from vectorize import CID_FIX

PDF_DIR = PROJECT / "data" / "pdfs"
DB_PATH = PROJECT / "data" / "rag.sqlite"
OUT_JSON = PROJECT / "data" / "pdf_cid_map.json"

MIN_PDF_FREQ = 10
RATIO_HIGH = 2.0
RATIO_LOW = 1.2
CN_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[\u4e00-\u9fff]+")

GOLD = {"亰": "人", "圃": "在", "乀": "之", "亍": "于", "夗": "多", "夛": "天",
        "斱": "方", "庖": "店", "迓": "还", "佝": "你", "巟": "工", "収": "发",
        "飠": "餐", "迖": "远"}


def load_pdf_texts() -> list[str]:
    import fitz
    texts = []
    for pdf in sorted(PDF_DIR.rglob("*.pdf")):
        try:
            doc = fitz.open(pdf)
            t = "\n".join(p.get_text() for p in doc)
            doc.close()
            texts.append(t.translate(CID_FIX))
        except Exception as e:
            logger.warning(f"  提取失败 {pdf.name}: {e}")
    logger.info(f"   提取 {len(texts)} 个 PDF")
    return texts


def load_clean_chunks() -> list[str]:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT chunk_text FROM whither_rag_embeddings WHERE source_type='mafengwo_free'"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def main():
    t0 = time.time()
    logger.info("① 提取 PDF 语料")
    pdf_cn = "".join(CN_RE.findall("".join(load_pdf_texts())))
    logger.info(f"   PDF 汉字 {len(pdf_cn):,}")

    logger.info("② 干净语料 + jieba 词表（合法字判定）")
    clean_chunks = load_clean_chunks()
    clean_cn = "".join(CN_RE.findall("\n".join(clean_chunks)))
    logger.info(f"   干净汉字 {len(clean_cn):,}")

    import jieba  # noqa: F401  仅取词典
    dictfile = Path(jieba.__file__).with_name("dict.txt")
    dict_words = set()
    for line in dictfile.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and WORD_RE.fullmatch(parts[0]):
            dict_words.add(parts[0])
    legal = {ch for w in dict_words for ch in w} | set(clean_cn) | set("的一是在了不和有大这人上中到说们")
    logger.info(f"   jieba 词条 {len(dict_words)}  合法字 {len(legal)}")

    logger.info("③ 错字候选筛选")
    fp = Counter(pdf_cn)
    candidates = {ch: n for ch, n in fp.items()
                  if n >= MIN_PDF_FREQ and ch not in legal}
    logger.info(f"   候选错字 {len(candidates)} 个，共 {sum(candidates.values()):,} 处")
    need = set(candidates)

    logger.info("④ 语料 bigram（PDF 自举剔除错字对 + 干净语料）+ 上下文收集")
    next_cnt = defaultdict(Counter)   # L -> {t: count}
    prev_cnt = defaultdict(Counter)   # R -> {t: count}
    ctx = defaultdict(list)           # 错字 -> [(L, R), ...]

    def feed(cn: str, collect: bool = False):
        a = cn[0]
        for i in range(1, len(cn)):
            b = cn[i]
            if collect and a in need and 0 < i < len(cn) - 1:
                ctx[a].append((cn[i - 1], cn[i + 1]))
            if a not in need and b not in need and a in legal and b in legal:
                next_cnt[a][b] += 1
                prev_cnt[b][a] += 1
            a = b

    feed(pdf_cn, collect=True)
    feed(clean_cn)
    logger.info(f"   bigram 字对 {sum(sum(c.values()) for c in next_cnt.values()):,}  上下文 {sum(len(v) for v in ctx.values()):,}")

    logger.info("⑤ 推断（score(t)=P(t|L)·P(t|R)，候选限制合法字）")
    mapping, low_conf, unmapped = {}, {}, []
    for ch, n in sorted(candidates.items(), key=lambda x: -x[1]):
        pairs = ctx.get(ch, [])
        if not pairs:
            unmapped.append(ch)
            continue
        score = Counter()
        for L, R in pairs:
            dn, dp = next_cnt.get(L), prev_cnt.get(R)
            if not dn and not dp:
                continue
            tn = sum(dn.values()) if dn else 0
            tp = sum(dp.values()) if dp else 0
            for t in (set(dn or ()) | set(dp or ())):
                p1 = ((dn or {}).get(t, 0) + 1) / (tn + len(legal))
                p2 = ((dp or {}).get(t, 0) + 1) / (tp + len(legal))
                score[t] += p1 * p2
        if not score:
            unmapped.append(ch)
            continue
        top = score.most_common(2)
        best, s1 = top[0]
        s2 = top[1][1] if len(top) > 1 else 0.0
        ratio = s1 / (s2 + 1e-12)
        rec = {"to": best, "score": round(s1, 8), "ratio": round(ratio, 2), "n": n}
        if ratio >= RATIO_HIGH:
            mapping[ch] = rec
        elif ratio >= RATIO_LOW:
            low_conf[ch] = rec
        else:
            unmapped.append(ch)

    logger.info("⑥ 自检（金标准 14 字）")
    hit, miss_ = 0, []
    for g, expect in GOLD.items():
        got = mapping.get(g, {}).get("to") or low_conf.get(g, {}).get("to")
        if got == expect:
            hit += 1
        else:
            miss_.append(f"{g}(→{expect},推{got})")
    logger.info(f"   金标准命中 {hit}/14")
    if miss_:
        logger.warning("   " + " ".join(miss_))

    for g, expect in GOLD.items():  # 人工确认强制覆盖
        mapping[g] = {"to": expect, "score": 1.0, "ratio": 999.0,
                      "n": candidates.get(g, 0), "gold": True}

    OUT_JSON.write_text(json.dumps(
        {"high": mapping, "low": low_conf, "unmapped": unmapped,
         "candidates_total": len(candidates),
         "occurrences": sum(candidates.values()), "gold_hit": f"{hit}/14"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    high_occ = sum(r["n"] for r in mapping.values())
    logger.info(f"💾 → {OUT_JSON}")
    logger.info(f"   高置信 {len(mapping)}（{high_occ:,} 处）  低置信 {len(low_conf)}（{sum(r['n'] for r in low_conf.values()):,} 处）  未定 {len(unmapped)}")
    logger.info(f"耗时 {time.time()-t0:.0f}s")

    if "--apply" in sys.argv:
        apply_mapping(mapping)


def apply_mapping(mapping: dict):
    """高置信映射写入 scripts/cid_fix_extra.py（vectorize.py 已 import）"""
    out = PROJECT / "scripts" / "cid_fix_extra.py"
    lines = ['"""PDF 乱码映射扩展表（scripts/fix_pdf_garble.py 自动生成，勿手改）"""',
             "", "CID_FIX_EXTRA = str.maketrans({"]
    for ch, rec in sorted(mapping.items()):
        esc = ch.encode("unicode_escape").decode()
        to = rec["to"].encode("unicode_escape").decode()
        lines.append(f'    "{ch}": "{to}",  # {esc} n={rec["n"]} ratio={rec["ratio"]}')
    lines.append("})")
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"✅ 扩展映射已写入 {out}（{len(mapping)} 条）")


if __name__ == "__main__":
    main()
