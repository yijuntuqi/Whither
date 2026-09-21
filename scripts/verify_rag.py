"""向量化结果验证 + 多城市检索测试"""
import json, sqlite3, time
import httpx

DB = "data/rag.sqlite"

# 1. 统计
with sqlite3.connect(DB) as conn:
    total = conn.execute("SELECT COUNT(*) FROM whither_rag_embeddings").fetchone()[0]
    cities = conn.execute("SELECT COUNT(DISTINCT city) FROM whither_rag_embeddings WHERE city != ''").fetchone()[0]
    by_source = conn.execute("SELECT source_type, COUNT(*) FROM whither_rag_embeddings GROUP BY source_type").fetchall()

print(f"总 chunk 数: {total}")
print(f"覆盖城市数: {cities}")
print(f"来源分布: {by_source}")

# 2. 检索测试
def search(query, top_k=3):
    t0 = time.time()
    r = httpx.post("http://localhost:11434/api/embeddings",
                   json={"model": "nomic-embed-text", "prompt": query}, timeout=30)
    q = r.json()["embedding"]

    import numpy as np
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, city, chunk_text, metadata, embedding_json FROM whither_rag_embeddings").fetchall()
    mat = np.array([json.loads(r["embedding_json"]) for r in rows], dtype=np.float32)
    qv = np.array(q, dtype=np.float32)
    scores = mat @ qv / (np.linalg.norm(mat, axis=1) * np.linalg.norm(qv) + 1e-8)
    top = np.argsort(-scores)[:top_k]

    print(f"\n🔍 '{query}'  (embed+search {time.time()-t0:.2f}s)")
    for i in top:
        meta = json.loads(rows[i]["metadata"])
        print(f"  [{scores[i]:.4f}] {rows[i]['city']} | {meta.get('title','')[:45]}")

search("成都有什么好吃的美食")
search("哈尔滨冬天看雪")
search("三亚海边度假")
