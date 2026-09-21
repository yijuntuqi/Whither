"""Neon 快速测试 - 如果 compute resume 了应该能连"""
import os, time
from dotenv import load_dotenv
load_dotenv()

import psycopg

url = os.getenv("NEON_DATABASE_URL")
print(f"尝试连接 Neon pooler...", flush=True)

# 先给更长的超时 + 多次重试
for attempt in range(1, 4):
    print(f"  尝试 {attempt}/3 (超时 60s)...", flush=True)
    start = time.time()
    try:
        params = psycopg.conninfo.conninfo_to_dict(url)
        params["connect_timeout"] = "60"
        params.pop("channel_binding", None)  # 去掉这个可能有问题的参数
        
        with psycopg.connect(**params) as conn:
            elapsed = time.time() - start
            with conn.cursor() as cur:
                cur.execute("SELECT 1, current_database(), version()")
                row = cur.fetchone()
                print(f"  ✅ 连接成功！耗时 {elapsed:.1f}s", flush=True)
                print(f"     DB: {row[1]}, Ver: {row[2].split(',')[0]}", flush=True)
                
                # 自动提交模式跑 DDL
                conn.autocommit = True
                cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")
                print(f"  ✅ lakebase_vector 扩展已启用", flush=True)
                
                # 检查 Whither 表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS whither_users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email TEXT UNIQUE NOT NULL,
                        api_key_encrypted TEXT,
                        api_key_iv TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS whither_rag_embeddings (
                        id BIGSERIAL PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        source_id TEXT,
                        city TEXT,
                        chunk_text TEXT NOT NULL,
                        embedding vector(768),
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS whither_rag_city_idx ON whither_rag_embeddings (city)")
                
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'whither_%'")
                tables = [r[0] for r in cur.fetchall()]
                print(f"  ✅ Whither 表已创建: {tables}", flush=True)
                print(f"\n🎉 M0 Neon 基建完成！", flush=True)
                
        break
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ 失败 ({elapsed:.1f}s): {e}", flush=True)
        if attempt < 3:
            wait = 30 * attempt
            print(f"  等待 {wait}s 后重试...", flush=True)
            time.sleep(wait)
