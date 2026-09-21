"""bge-m3 吞吐优化基准：不同 batch_size + 并发路数。
用法: E:\\conda_envs\\langchain\\python.exe scripts/bench_embed.py
"""
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vectorize import OllamaEmbedder

conn = sqlite3.connect("data/rag.sqlite")
N = 64
rows = conn.execute(
    "SELECT chunk_text FROM whither_rag_embeddings ORDER BY RANDOM() LIMIT ?", (N,)
).fetchall()
texts = [r[0] for r in rows]
print(f"样本 {N} 条（每条件跑完）\n")

# 预热（模型加载不计入）
e0 = OllamaEmbedder()
e0.embed_batch(texts[:8])


def bench_batch(size):
    e = OllamaEmbedder()
    t0 = time.time()
    e.embed_batch(texts, batch_size=size)
    dt = time.time() - t0
    print(f"单路 batch={size:<3}: {dt:5.1f}s  {N/dt:5.2f} 条/秒")
    return N / dt


def bench_parallel(workers, size):
    chunks = [texts[i::workers] for i in range(workers)]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(
            lambda c: OllamaEmbedder().embed_batch(c, batch_size=size), chunks))
    dt = time.time() - t0
    print(f"{workers} 路并发 batch={size}: {dt:5.1f}s  {N/dt:5.2f} 条/秒")
    return N / dt


best = 0
for size in (8, 16, 64):
    best = max(best, bench_batch(size))
for workers, size in ((2, 16), (4, 16), (2, 32)):
    best = max(best, bench_parallel(workers, size))

print(f"\n最优吞吐: {best:.2f} 条/秒 → 全量 8980 条预计 {8980/best/60:.0f} 分钟")
