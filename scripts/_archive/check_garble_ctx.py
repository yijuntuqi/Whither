"""检查残留 16 处乱码字（圃、亍）的上下文，判断是真字还是 OCR 误识"""
import sqlite3

with sqlite3.connect("data/rag.sqlite") as conn:
    rows = conn.execute(
        "SELECT chunk_text FROM whither_rag_embeddings "
        "WHERE source_type='pdf' AND (chunk_text LIKE '%圃%' OR chunk_text LIKE '%亍%')"
    ).fetchall()

print(f"含残留字的 chunk 数: {len(rows)}")
seen = set()
for (text,) in rows:
    for ch in "圃亍":
        start = 0
        while True:
            idx = text.find(ch, start)
            if idx < 0:
                break
            ctx = text[max(0, idx - 10):idx + 10]
            if ctx not in seen:
                seen.add(ctx)
                print(f"  「{ch}」: ...{ctx}...")
            start = idx + 1
