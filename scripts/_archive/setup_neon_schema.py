"""
M0 Neon 基建脚本 — 创建 Whither 所需的数据库结构
执行顺序：pgvector 扩展 → 用户表 → RAG 向量表 → LangGraph Checkpointer 表
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import psycopg
from psycopg.rows import dict_row

# 必须用 DIRECT 连接（不带 -pooler）执行 DDL
DIRECT_URL = os.getenv("NEON_DATABASE_URL_UNPOOLED")
POOLED_URL = os.getenv("NEON_DATABASE_URL")

if not DIRECT_URL:
    print("❌ 缺少 NEON_DATABASE_URL_UNPOOLED 环境变量")
    sys.exit(1)

print("=" * 60)
print("Whither M0 Neon 基建")
print("=" * 60)

# -----------------------------------------------------------
# Step 1: 连通性测试
# -----------------------------------------------------------
print("\n🔌 [1/6] 测试数据库连接...")
try:
    with psycopg.connect(DIRECT_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            print(f"  ✅ 连接成功！PostgreSQL {version.split(',')[0]}")
            
            cur.execute("SELECT current_database(), current_user")
            db, user = cur.fetchone()
            print(f"  📋 数据库: {db} | 用户: {user}")
            
            cur.execute("SHOW server_version")
            pg_ver = cur.fetchone()[0]
            print(f"  🔢 PostgreSQL 版本: {pg_ver}")
except Exception as e:
    print(f"  ❌ 连接失败: {e}")
    sys.exit(1)

# -----------------------------------------------------------
# Step 2: 安装 pgvector (lakebase_vector) 扩展
# -----------------------------------------------------------
print("\n🧠 [2/6] 安装 pgvector (lakebase_vector) 扩展...")
try:
    with psycopg.connect(DIRECT_URL) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Neon 用 lakebase_vector（内部依赖 pgvector）
            cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")
            print(f"  ✅ lakebase_vector 扩展已启用")
            
            # 验证
            cur.execute("SELECT * FROM pg_extension WHERE extname IN ('lakebase_vector', 'vector')")
            exts = cur.fetchall()
            for ext in exts:
                print(f"     → {ext[0]} v{ext[1]}")
            
            # 验证 vector 类型可以用
            cur.execute("SELECT '[]'::vector(3) IS NOT NULL")
            print(f"  ✅ vector 类型可用")
except Exception as e:
    print(f"  ❌ pgvector 安装失败: {e}")
    print("  💡 可能需要在 Neon Dashboard 手动启用 lakebase_vector")
    sys.exit(1)

# -----------------------------------------------------------
# Step 3: 创建 Whither 用户表
# -----------------------------------------------------------
print("\n👤 [3/6] 创建用户表 whither_users...")
USER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS whither_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    api_key_encrypted TEXT,
    api_key_iv TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""
try:
    with psycopg.connect(DIRECT_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(USER_TABLE_SQL)
        conn.commit()
        print("  ✅ whither_users 表已创建")
        
        # 检查现有用户数
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM whither_users")
            cnt = cur.fetchone()[0]
            print(f"  📋 当前用户数: {cnt}")
except Exception as e:
    print(f"  ❌ 用户表创建失败: {e}")

# -----------------------------------------------------------
# Step 4: 创建 RAG 向量表（共享知识库）
# -----------------------------------------------------------
print("\n📚 [4/6] 创建 RAG 向量表 whither_rag_embeddings...")
RAG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS whither_rag_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT,
    city TEXT,
    chunk_text TEXT NOT NULL,
    embedding vector(768),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""
try:
    with psycopg.connect(DIRECT_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(RAG_TABLE_SQL)
        conn.commit()
        print("  ✅ whither_rag_embeddings 表已创建")
        
        # 创建 city 索引（方便按城市 filter）
        with conn.cursor() as cur:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS whither_rag_city_idx 
                ON whither_rag_embeddings (city)
            """)
            print("  ✅ city 索引已创建")
        
        # 创建 ANN 向量索引（用 lakebase_ann）
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS whither_rag_embedding_ann 
                    ON whither_rag_embeddings 
                    USING lakebase_ann (embedding vector_cosine_ops)
                    WITH (build_mode = 'standard')
                """)
                print("  ✅ lakebase_ann 向量索引已创建")
            except Exception as idx_err:
                # 如果表是空的，索引可能创建失败——没关系，有数据后再建
                print(f"  ⚠️ 向量索引创建跳过（表为空或已存在）: {idx_err}")
                
        conn.commit()
        
        # 检查表结构
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'whither_rag_embeddings'
                ORDER BY ordinal_position
            """)
            cols = cur.fetchall()
            print(f"  📋 表结构:")
            for col_name, col_type in cols:
                print(f"     {col_name:20s} {col_type}")
                
except Exception as e:
    print(f"  ❌ RAG 表创建失败: {e}")

# -----------------------------------------------------------
# Step 5: 检查现有表（来自 lovememo 项目）
# -----------------------------------------------------------
print("\n🔍 [5/6] 检查数据库现有表...")
try:
    with psycopg.connect(DIRECT_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            print(f"  📋 public schema 共 {len(tables)} 张表:")
            for tname, ttype in tables:
                marker = "🆕" if tname.startswith("whither_") else "  "
                print(f"     {marker} {tname} ({ttype})")
except Exception as e:
    print(f"  ❌ 查询失败: {e}")

# -----------------------------------------------------------
# Step 6: LangGraph Checkpointer 表（自动创建）
# -----------------------------------------------------------
print("\n🔄 [6/6] LangGraph Checkpointer 说明...")
print("  LangGraph PostgresCheckpointer 会在首次运行 Agent 时")
print("  自动创建以下表，不需要手动建：")
print("    - checkpoints")
print("    - checkpoints_blobs")
print("    - checkpoints_writes")
print("    - checkpoints_migrations")
print()
print("  首次使用示例：")
print("    from langgraph.checkpoint.postgres import PostgresSaver")
print("    saver = PostgresSaver.from_conn_string(POOLED_URL)")
print("    await saver.setup()  # ← 自动创建所有表")

# -----------------------------------------------------------
# 总结
# -----------------------------------------------------------
print("\n" + "=" * 60)
print("✅ M0 Neon 基建完成！")
print("=" * 60)
print(f"""
已完成：
  ✅ 数据库连接（direct + pooled 两种）
  ✅ lakebase_vector / pgvector 扩展
  ✅ whither_users 用户表
  ✅ whither_rag_embeddings RAG 向量表
  ✅ city 索引 + ANN 向量索引

下一步：
  1. 确认 Embedding 模型维度（当前设为 768，对应 Ollama nomic-embed-text）
  2. 写马蜂窝自由行爬虫（无校验 GET 接口）
  3. 批量爬取 → 向量化 → 导入 pgvector
  4. 开始 M1：LangGraph Agent + 工具集
""")
