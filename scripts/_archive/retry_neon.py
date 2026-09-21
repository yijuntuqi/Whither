"""重试 Neon 连接 - compute 应该活了"""
import os, time
from dotenv import load_dotenv
load_dotenv()

import psycopg

url = os.getenv("NEON_DATABASE_URL")  # pooler
params = psycopg.conninfo.conninfo_to_dict(url)
params["connect_timeout"] = "30"
params.pop("channel_binding", None)

print(f"连接 Neon pooler...", flush=True)
start = time.time()
try:
    with psycopg.connect(**params) as conn:
        elapsed = time.time() - start
        with conn.cursor() as cur:
            cur.execute("SELECT 1, current_database(), version()")
            row = cur.fetchone()
            print(f"✅ 连接成功！耗时 {elapsed:.1f}s", flush=True)
            print(f"   DB: {row[1]}", flush=True)
            print(f"   Ver: {row[2].split(',')[0]}", flush=True)
            
            cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('lakebase_vector', 'vector')")
            print(f"   扩展: {[r[0] for r in cur.fetchall()]}", flush=True)
            
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'whither_%'")
            print(f"   Whither 表: {[r[0] for r in cur.fetchall()]}", flush=True)
except Exception as e:
    elapsed = time.time() - start
    print(f"❌ 失败 ({elapsed:.1f}s): {e}", flush=True)
