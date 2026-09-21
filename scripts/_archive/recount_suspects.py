"""复测脚本：频率对比法统计 PDF 乱码残留
口径：某字符在 OCR PDF 语料中出现 >=20 次，且在干净语料（mafengwo_free chunk）中出现 0 次
→ 记为可疑字符。验收目标：可疑字符数 < 10。
用法: python scripts/_archive/recount_suspects.py            # 统计 data/ocr_texts/
      python scripts/_archive/recount_suspects.py --pdf-fitZ # 对照：旧 fitz 提取文本（data/pdfs 直读，可选）"""
import argparse
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from dotenv import load_dotenv

load_dotenv()

ROOT = Path.cwd()
DB = ROOT / "data" / "rag.sqlite"
OCR_DIR = ROOT / "data" / "ocr_texts"
CJK = re.compile(r"[\u4e00-\u9fff]")


def load_clean_counter() -> Counter:
    """干净语料：mafengwo_free 的 chunk_text 字符频率"""
    cnt = Counter()
    with sqlite3.connect(DB) as conn:
        for (text,) in conn.execute(
                "SELECT chunk_text FROM whither_rag_embeddings WHERE source_type='mafengwo_free'"):
            cnt.update(c for c in text if CJK.match(c))
    return cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20, help="展示可疑字符 TOP N")
    args = ap.parse_args()

    clean = load_clean_counter()
    print(f"干净语料字符数: {sum(clean.values()):,}  种类: {len(clean):,}")

    pdf_cnt = Counter()
    files = sorted(OCR_DIR.glob("*.txt")) if OCR_DIR.exists() else []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        pdf_cnt.update(c for c in text if CJK.match(c))
    total = sum(pdf_cnt.values())
    print(f"PDF(OCR) 语料: {len(files)} 文件  字符数 {total:,}  种类 {len(pdf_cnt):,}")

    suspects = {ch: n for ch, n in pdf_cnt.items() if n >= 20 and clean.get(ch, 0) == 0}
    print(f"\n=== 可疑字符（PDF>=20 且 干净语料=0）: {len(suspects)} 个，验收目标 <10 ===")
    for ch, n in sorted(suspects.items(), key=lambda x: -x[1])[:args.top]:
        print(f"  {ch} U+{ord(ch):04X}: PDF {n} 次")
    if len(suspects) < 10:
        print("\n✅ 验收通过")
    else:
        print("\n❌ 未达标，需排查上方字符来源")
    return 0 if len(suspects) < 10 else 1


if __name__ == "__main__":
    sys.exit(main())
