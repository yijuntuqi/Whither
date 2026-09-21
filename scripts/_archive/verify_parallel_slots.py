"""验证 OLLAMA_NUM_PARALLEL=2 双 slot 下的并发吞吐。
用法: E:\\conda_envs\\langchain\\python.exe scripts/verify_parallel_slots.py
"""
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vectorize import OllamaEmbedder

conn = sqlite3.connect("data/rag.sqlite")
rows = conn.execute(
    "SELECT chunk_text FROM whither_rag_embeddings ORDER BY RANDOM() LIMIT 160"
).fetchall()
texts = [r[0] for r in rows]


def run_parallel(items, workers, size):
    chunks = [items[i::workers] for i in range(workers)]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(
            lambda c: OllamaEmbedder().embed_batch(c, batch_size=size), chunks))
    return time.time() - t0


# 预热：并发让两个 slot 都加载模型
run_parallel(texts[:16], 2, 8)
print("双 slot 预热完成\n")

dt1 = run_parallel(texts[16:80], 1, 32)
print(f"单路 64 条: {dt1:5.1f}s  {64/dt1:5.2f} 条/秒")
dt2 = run_parallel(texts[80:], 2, 16)
print(f"双路 64 条: {dt2:5.1f}s  {64/dt2:5.2f} 条/秒")
print(f"\n双slot 加速比: {dt1/dt2:.2f}x")
print(f"全量 8980 条按双路预计: {8980/(64/dt2)/60:.0f} 分钟")
