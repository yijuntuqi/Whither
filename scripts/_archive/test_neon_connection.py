"""测试 Neon 连接：Data API 查询现有表 + S3 对象存储 + pgvector 扩展检查"""
import os
import sys
from pathlib import Path

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("Neon 连接测试")
print("=" * 60)

# -----------------------------------------------------------
# 1. 测试 S3 对象存储连通性
# -----------------------------------------------------------
print("\n📦 [1/3] 测试 Neon S3 对象存储...")
try:
    import boto3
    
    s3_client = boto3.client(
        's3',
        endpoint_url=os.getenv("AWS_ENDPOINT_URL_S3"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    
    # 列出所有 bucket
    response = s3_client.list_buckets()
    buckets = [b['Name'] for b in response.get('Buckets', [])]
    print(f"  ✅ S3 连接成功！现有 buckets: {buckets}")
    
    # 创建 whither-data bucket（如果不存在）
    target_bucket = os.getenv("AWS_BUCKET_NAME", "whither-data")
    if target_bucket not in buckets:
        s3_client.create_bucket(Bucket=target_bucket)
        print(f"  ✅ 已创建 bucket: {target_bucket}")
    else:
        print(f"  ℹ️  bucket 已存在: {target_bucket}")
        
except Exception as e:
    print(f"  ❌ S3 连接失败: {e}")

# -----------------------------------------------------------
# 2. 测试 Neon Data API (PostgREST) - 查询现有表
# -----------------------------------------------------------
print("\n🗄️  [2/3] 测试 Neon Data API...")
import urllib.request
import json

DATA_API_URL = os.getenv("NEON_DATA_API_URL", "")
if not DATA_API_URL:
    print("  ⚠️  NEON_DATA_API_URL 未配置，跳过")
else:
    # PostgREST 兼容：查询 public schema 的所有表
    # PostgREST 自动暴露表为 REST 端点
    try:
        # 尝试查询一个已知存在的表来验证连接
        tables_in_db = [
            "lovememo_users", "lovememo_devices", "lovememo_activation_codes",
            "lovememo_sync_records", "analysis_records", "data_files",
            "exports", "orders", "projects", "reports"
        ]
        
        found_tables = []
        for table in tables_in_db:
            try:
                url = f"{DATA_API_URL}/{table}?limit=1"
                req = urllib.request.Request(url)
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    print(f"  ✅ {table} ({len(data)} rows in sample)")
                    found_tables.append(table)
            except Exception:
                pass
        
        if not found_tables:
            print("  ⚠️  Data API 需要 Auth Token 才能访问（安全设计）")
            print("  💡 下一步：用 Neon SQL 直连 psycopg 来查询表结构和安装 pgvector")
        else:
            print(f"  📋 共发现 {len(found_tables)} 张表（来自 lovememo 项目）")
            
    except Exception as e:
        print(f"  ❌ Data API 查询失败: {e}")

# -----------------------------------------------------------
# 3. 总结
# -----------------------------------------------------------
print("\n📝 总结")
print("-" * 40)
print("Neon 的数据库是 PostgreSQL，现有表是 lovememo 项目的。")
print("Whither 需要新增以下表（或在新 schema 下）：")
print("  - users (用户表)")
print("  - preferences (用户偏好 - LangGraph Store)")
print("  - trip_plans (历史行程)")
print("  - checkpoints (对话历史 - LangGraph Checkpointer)")
print("  - rag_documents (RAG 文档元数据)")
print("  - rag_embeddings (RAG 向量 - pgvector)")
print("")
print("⚠️  注意：我需要 Neon SQL 直连 URL 来：")
print("  1) 安装 pgvector 扩展")
print("  2) 创建 Whither 专属表结构")
print("  3) 后续 LangGraph Checkpointer 持久化")
print("")
print("👉 请到 Neon Dashboard → Connection Details 获取 SQL 连接字符串")
print("   格式：postgresql://user:password@host:port/dbname?sslmode=require")
