"""
Neon 连接重试 + S3 验证（2026-09-19）
1. psycopg 连接（pooler / direct）
2. boto3 S3 ListBuckets（之前没跑通，现在用官方 .env 格式重试）
"""
import os, time
from dotenv import load_dotenv

load_dotenv()

import psycopg

POOLER = os.getenv("NEON_DATABASE_URL", "").replace("&channel_binding=require", "")
DIRECT = os.getenv("NEON_DATABASE_URL_UNPOOLED", "").replace("&channel_binding=require", "")

print("=" * 50)
print("1) Neon psycopg 连接测试")
for name, url in [("pooler", POOLER), ("direct", DIRECT)]:
    if not url:
        print(f"  {name}: URL 为空，跳过")
        continue
    t0 = time.time()
    try:
        params = psycopg.conninfo.conninfo_to_dict(url)
        params["connect_timeout"] = "15"
        with psycopg.connect(**params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                v = cur.fetchone()[0]
            print(f"  ✅ {name} OK ({time.time()-t0:.1f}s): {v[:50]}")
            # 顺便查 pgvector 和表
            with conn.cursor() as cur:
                cur.execute("SELECT extname FROM pg_extension WHERE extname LIKE '%vector%'")
                exts = [r[0] for r in cur.fetchall()]
                print(f"     vector 扩展: {exts}")
                cur.execute("""SELECT table_name FROM information_schema.tables
                               WHERE table_schema='public' AND table_name LIKE 'whither%'""")
                tables = [r[0] for r in cur.fetchall()]
                print(f"     whither 表: {tables}")
    except Exception as e:
        print(f"  ❌ {name} FAIL ({time.time()-t0:.1f}s): {type(e).__name__}: {str(e)[:120]}")

print()
print("=" * 50)
print("2) Neon S3 ListBuckets")
try:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL_S3"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )
    t0 = time.time()
    resp = s3.list_buckets()
    names = [b["Name"] for b in resp.get("Buckets", [])]
    print(f"  ✅ OK ({time.time()-t0:.1f}s) buckets: {names}")
except Exception as e:
    print(f"  ❌ FAIL: {type(e).__name__}: {str(e)[:200]}")
