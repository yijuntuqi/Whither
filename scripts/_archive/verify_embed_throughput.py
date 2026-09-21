"""② 验收：bge-m3 /api/embed 批量吞吐（32 条真实 chunk 计时）。
用法: E:\\conda_envs\\langchain\\python.exe scripts/verify_embed_throughput.py
"""
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vectorize import OllamaEmbedder

conn = sqlite3.connect("data/rag.sqlite")
rows = conn.execute(
    "SELECT chunk_text FROM whither_rag_embeddings ORDER BY RANDOM() LIMIT 64"
).fetchall()
texts = [r[0] for r in rows]
print(f"取样 {len(texts)} 条真实 chunk，模型: bge-m3, batch=32")

embedder = OllamaEmbedder()

# 第一批含模型冷启动加载；第二批为稳态吞吐
t0 = time.time()
embedder.embed_batch(texts[:32])
cold = time.time() - t0
print(f"第 1 批（含冷启动）: {cold:.1f}s, {32/cold:.2f} 条/秒")

t0 = time.time()
embedder.embed_batch(texts[32:])
warm = time.time() - t0
tput = 32 / warm
print(f"第 2 批（稳态）: {warm:.1f}s, {tput:.2f} 条/秒")

# 维度确认
v = embedder.embed("维度测试")
print(f"维度: {len(v)}")
if tput > 5:
    print(f"✅ ② 验收通过：稳态吞吐 {tput:.2f} > 5 条/秒")
else:
    print(f"⚠️ 稳态吞吐 {tput:.2f} 未达 5 条/秒（全量重跑预计 {8980/tput/60:.0f} 分钟）")
