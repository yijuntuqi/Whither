"""④ 全量重建验收（监工三条：维度唯一且=1024 / 乱码=0 / 实调检索）
用法: E:\\conda_envs\\langchain\\python.exe scripts/verify_rebuild.py
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vectorize import count_suspect  # noqa: E402

conn = sqlite3.connect(ROOT / "data" / "rag.sqlite")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT source_type, city, embedding_json, chunk_text FROM whither_rag_embeddings"
).fetchall()

# 验收 1：维度分布——只剩一行且 = 1024
dims: dict = {}
for r in rows:
    v = r["embedding_json"]
    d = len(v) // 4 if isinstance(v, (bytes, memoryview)) else len(json.loads(v))
    dims[d] = dims.get(d, 0) + 1
print(f"1) 维度分布: {dims} {'✅' if list(dims) == [1024] else '❌'}")
print(f"   source_type: {dict(Counter(r['source_type'] for r in rows))}")
print(f"   总数: {len(rows)}")

# 验收 2：PDF chunk 可疑乱码字符数 = 0
# （CID_FIX 只作用于 PDF 文本；mafengwo 爬虫文本中"俱/丌"等可能为正常用字，不在扫描范围）
pdf_rows = [r for r in rows if r["source_type"] == "pdf"]
bad_chars = sum(count_suspect(r["chunk_text"]) for r in pdf_rows)
bad_chunks = sum(1 for r in pdf_rows if count_suspect(r["chunk_text"]))
print(f"2) 乱码: 可疑字符 {bad_chars} / 受影响 chunk {bad_chunks} "
      f"{'✅' if bad_chars == 0 else '❌'}")

# 验收 3：实调一次 search_travel_knowledge（走 agent tool 全链路）
from backend.app.agent.tools import search_travel_knowledge  # noqa: E402

out = search_travel_knowledge.func(query="成都三日游怎么安排", city="成都")
print("3) search_travel_knowledge 返回:")
print("\n".join(out.splitlines()[:8]))
ok3 = "没有找到" not in out and len(out.strip()) > 50
print(f"   {'✅ 3) 检索正常' if ok3 else '❌ 3) 检索异常'}")

sys.exit(0 if (list(dims) == [1024] and bad_chars == 0 and ok3) else 1)
