"""快速测试 Neon 连接 + 建表 — 输出到文件"""
import os, sys
from dotenv import load_dotenv
load_dotenv()

out = open("scripts/test_result.txt", "w", encoding="utf-8")

def log(msg):
    print(msg)
    out.write(msg + "\n")
    out.flush()

log("=" * 50)
log("Whither M0 Neon 基建测试")
log("=" * 50)

import psycopg

url = os.getenv("NEON_DATABASE_URL_UNPOOLED")
log(f"URL: {url[:60]}...")

try:
    with psycopg.connect(url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            log("✅ 连接成功")
            
            log("\n[1/4] 安装 lakebase_vector 扩展...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")
            log("✅ lakebase_vector 已启用")
            
            cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('lakebase_vector', 'vector')")
            log(f"📦 扩展列表: {[r[0] for r in cur.fetchall()]}")
            
            log("\n[2/4] 创建 whither_users 表...")
            cur.execute("CREATE TABLE IF NOT EXISTS whither_users (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email TEXT UNIQUE NOT NULL, api_key_encrypted TEXT, api_key_iv TEXT, created_at TIMESTAMPTZ DEFAULT NOW())")
            log("✅ whither_users 表已创建")
            
            log("\n[3/4] 创建 whither_rag_embeddings 表...")
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
            log("✅ whither_rag_embeddings 表已创建")
            
            cur.execute("CREATE INDEX IF NOT EXISTS whither_rag_city_idx ON whither_rag_embeddings (city)")
            log("✅ city 索引已创建")
            
            log("\n[4/4] 验证表结构...")
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'whither_%' ORDER BY table_name")
            tables = cur.fetchall()
            log(f"📋 Whither 相关表 ({len(tables)} 个):")
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM {t[0]}")
                cnt = cur.fetchone()[0]
                log(f"   ✅ {t[0]:35s} ({cnt} rows)")
                
            log("\n🎉 M0 Neon 基建完成！")
                
except Exception as e:
    import traceback
    log(f"\n❌ 失败: {e}")
    log(traceback.format_exc())
finally:
    out.close()
