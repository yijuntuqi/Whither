"""
用 Neon 官方 Python SDK / Data API 测试连接
替代 psycopg（可能 pooler SSL 握手有问题）
"""
import os, json, time
from dotenv import load_dotenv
load_dotenv()

import httpx

DATA_API = os.getenv("NEON_DATA_API_URL", "").rstrip("/")

print(f"测试 Neon Data API (PostgREST 兼容)...")
print(f"URL: {DATA_API}")

# Data API 不需要额外 token（Neon 托管 Auth 后自动带）
# 先试试直接查询 whither_rag_embeddings 表
urls = [
    f"{DATA_API}/whither_rag_embeddings?limit=1",
    f"{DATA_API}/whither_users?limit=1",
    f"{DATA_API}/whither_rag_embeddings?select=id,source_type&limit=1",
]

for url in urls:
    try:
        resp = httpx.get(url, timeout=15.0)
        print(f"\nGET {url.split('rest/v1/')[1]}")
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.text[:200]}")
    except Exception as e:
        print(f"\n❌ {url}: {e}")

# 试试 SQL 通过 RPC（PostgREST 支持 rpc 端点）
print(f"\n--- 试试 rpc ---")
rpc_url = f"{DATA_API}/rpc?select=1"
try:
    resp = httpx.get(rpc_url, timeout=15.0)
    print(f"GET rpc?select=1: {resp.status_code} | {resp.text[:200]}")
except Exception as e:
    print(f"❌ rpc: {e}")
