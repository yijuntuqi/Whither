"""测试城市过滤检索"""
import json, sqlite3, time
import httpx
import numpy as np

DB = "data/rag.sqlite"

def search(query, city=None, top_k=3):
    r = httpx.post("http://localhost:11434/api/embeddings",
                   json={"model": "nomic-embed-text", "prompt": query}, timeout=30)
    qv = np.array(r.json()["embedding"], dtype=np.float32)

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        if city:
            rows = conn.execute("SELECT city, chunk_text, metadata, embedding_json FROM whither_rag_embeddings WHERE city=?", (city,)).fetchall()
        else:
            rows = conn.execute("SELECT city, chunk_text, metadata, embedding_json FROM whither_rag_embeddings").fetchall()
    mat = np.array([json.loads(r["embedding_json"]) for r in rows], dtype=np.float32)
    scores = mat @ qv / (np.linalg.norm(mat, axis=1) * np.linalg.norm(qv) + 1e-8)
    top = np.argsort(-scores)[:top_k]
    label = f"[{city}]" if city else "[全库]"
    print(f"\n🔍 {label} '{query}'")
    for i in top:
        meta = json.loads(rows[i]["metadata"])
        print(f"  [{scores[i]:.4f}] {rows[i]['city']} | {meta.get('title','')[:45]}")

# 城市过滤：解决跨城市语义干扰
search("冬天看雪玩雪", city="哈尔滨")
search("冬天看雪玩雪", city="九寨沟")
search("美食小吃", city="成都")
search("海岛度假", city="三亚")
