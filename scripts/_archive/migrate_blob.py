"""跑批收尾后的一次性数据库迁移（孤儿行清理 + JSON→BLOB + 空间回收）
用法: E:\\conda_envs\\langchain\\python.exe scripts/migrate_blob.py
须在 vectorize 全量跑批结束并正常退出后执行。
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "rag.sqlite"
DIM = 1024  # bge-m3

size_before = DB.stat().st_size / 1048576
print(f"库文件: {DB} ({size_before:.0f} MB)")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# 1) 清理旧维度孤儿行（768 维 nomic 残留；混维矩阵会让检索崩溃）
orphans = conn.execute(
    "SELECT COUNT(*) FROM whither_rag_embeddings "
    "WHERE typeof(embedding_json) = 'text' AND json_array_length(embedding_json) <> ?",
    (DIM,),
).fetchone()[0]
if orphans:
    conn.execute(
        "DELETE FROM whither_rag_embeddings "
        "WHERE typeof(embedding_json) = 'text' AND json_array_length(embedding_json) <> ?",
        (DIM,),
    )
    conn.commit()
print(f"1) 删除异维孤儿行: {orphans}")

# 2) JSON 文本 → float32 BLOB（维度不对/解析失败的行一并剔除）
rows = conn.execute(
    "SELECT id, embedding_json FROM whither_rag_embeddings "
    "WHERE typeof(embedding_json) = 'text'"
).fetchall()
converted = bad = 0
for r in rows:
    try:
        vec = np.asarray(json.loads(r["embedding_json"]), dtype=np.float32)
        if vec.size != DIM:
            bad += 1
            conn.execute("DELETE FROM whither_rag_embeddings WHERE id=?", (r["id"],))
            continue
        conn.execute(
            "UPDATE whither_rag_embeddings SET embedding_json=? WHERE id=?",
            (vec.tobytes(), r["id"]),
        )
        converted += 1
    except (ValueError, TypeError):
        bad += 1
        conn.execute("DELETE FROM whither_rag_embeddings WHERE id=?", (r["id"],))
conn.commit()
print(f"2) JSON→BLOB: 转换 {converted} 行，剔除异常 {bad} 行")

# 3) 维度分布终检（BLOB: 字节数/4；残留 JSON: 数组长度）
dims: dict = {}
for (val,) in conn.execute("SELECT embedding_json FROM whither_rag_embeddings"):
    d = len(val) // 4 if isinstance(val, (bytes, memoryview)) else len(json.loads(val))
    dims[d] = dims.get(d, 0) + 1
print(f"3) 维度分布: {dims}")

# 4) 空间回收 + 完整性
conn.execute("VACUUM")
conn.close()
size_after = DB.stat().st_size / 1048576
print(f"4) VACUUM: {size_before:.0f} MB → {size_after:.0f} MB")
ic = sqlite3.connect(DB).execute("PRAGMA integrity_check").fetchone()[0]
print(f"5) integrity_check: {ic}")

ok = list(dims.keys()) == [DIM] and ic == "ok"
print("✅ 迁移完成" if ok else "❌ 迁移异常，请检查")
sys.exit(0 if ok else 1)
