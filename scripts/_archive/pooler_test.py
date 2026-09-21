"""测试 Neon pooler 连接 - pooler 一直在线会帮唤醒 compute"""
import os, time
from dotenv import load_dotenv
load_dotenv()

out = open("scripts/pooler_result.txt", "w", encoding="utf-8")
def log(m): print(m); out.write(m + "\n"); out.flush()

log("Neon Pooler 连接测试（推荐方式）")
log("=" * 50)

import psycopg

# 1. 先试 pooler URL
pooler_url = os.getenv("NEON_DATABASE_URL")
log(f"\n[1] 测试 Pooler 连接...")
log(f"    URL: {pooler_url[:70]}...")

params = psycopg.conninfo.conninfo_to_dict(pooler_url)
params["connect_timeout"] = "30"
params["options"] = "-c channel_binding=require"

start = time.time()
try:
    with psycopg.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1, current_database(), version()")
            row = cur.fetchone()
            elapsed = time.time() - start
            log(f"    ✅ Pooler 连接成功！耗时 {elapsed:.1f}s")
            log(f"    DB: {row[1]}")
            
            # 启用扩展
            log(f"\n[2] 启用 pgvector 扩展...")
            conn.autocommit = True
            cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")
            log(f"    ✅ lakebase_vector 已启用")
            
            cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('lakebase_vector', 'vector')")
            log(f"    📦 扩展: {[r[0] for r in cur.fetchall()]}")
            
            # 建表
            log(f"\n[3] 创建 Whither 表...")
            conn.autocommit = False
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
            conn.commit()
            log(f"    ✅ whither_users + whither_rag_embeddings 表已创建")
            
            cur.execute("CREATE INDEX IF NOT EXISTS whither_rag_city_idx ON whither_rag_embeddings (city)")
            conn.commit()
            log(f"    ✅ city 索引已创建")
            
            # 验证
            log(f"\n[4] 验证表结构...")
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'whither_%' ORDER BY table_name")
            tables = cur.fetchall()
            log(f"    📋 Whither 表 ({len(tables)}):")
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM {t[0]}")
                cnt = cur.fetchone()[0]
                log(f"       ✅ {t[0]:30s} ({cnt} rows)")
                
            log(f"\n🎉 M0 Neon 基建完成！")
                
except Exception as e:
    elapsed = time.time() - start
    import traceback
    log(f"    ❌ Pooler 连接失败（{elapsed:.1f}s）: {e}")
    log(traceback.format_exc())
    
    # 试试不带 channel_binding
    log(f"\n[备选] 去掉 channel_binding 再试...")
    try:
        clean_url = pooler_url.replace("&channel_binding=require", "")
        params2 = psycopg.conninfo.conninfo_to_dict(clean_url)
        params2["connect_timeout"] = "30"
        start2 = time.time()
        with psycopg.connect(**params2) as conn2:
            elapsed2 = time.time() - start2
            log(f"    ✅ 连接成功！耗时 {elapsed2:.1f}s")
    except Exception as e2:
        log(f"    ❌ 也失败了: {e2}")

out.close()
