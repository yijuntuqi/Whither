"""验证 OCR 后原始 14 个乱码字的残留 + 抽样确认可疑字为正常汉字"""
import re
import sqlite3
from pathlib import Path
from collections import Counter

DB = Path("data/rag.sqlite")
garble = "亰圃乀亍夗夛斱庖迓佝巟収飠迖"

pdf_cnt = Counter()
samples = {}
with sqlite3.connect(DB) as conn:
    for (text,) in conn.execute(
            "SELECT chunk_text FROM whither_rag_embeddings WHERE source_type='pdf'"):
        pdf_cnt.update(text)
        for ch in "医乎尤邻阔":
            if ch not in samples and ch in text:
                idx = text.find(ch)
                samples[ch] = text[max(0, idx - 12):idx + 12]

print("=== 原始 14 个乱码字在 OCR PDF 中的残留 ===")
total = 0
for ch in garble:
    n = pdf_cnt.get(ch, 0)
    total += n
    if n:
        print(f"  {ch} (U+{ord(ch):04X}): {n} 次")
print(f"合计残留: {total}  (期望 0)")

print("\n=== 可疑字抽样上下文（确认是正常汉字）===")
for ch, ctx in samples.items():
    print(f"  {ch}: ...{ctx}...")
