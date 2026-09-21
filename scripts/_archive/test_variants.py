"""全面尝试 Neon 连接 - 各种组合"""
import os, time, socket
from dotenv import load_dotenv
load_dotenv()

import psycopg

# 用户给的两个 URL
pooler_url = os.getenv("NEON_DATABASE_URL")
direct_url = os.getenv("NEON_DATABASE_URL_UNPOOLED")

# 清理 URL（去掉 channel_binding，换更短的超时）
def clean(url):
    return url.replace("&channel_binding=require", "").replace("?sslmode=require&", "?sslmode=require&connect_timeout=15&")

# 也试试不带任何 sslmode 参数的版本
def no_ssl(url):
    return url.replace("?sslmode=require&channel_binding=require", "?connect_timeout=15").replace("?sslmode=require", "?connect_timeout=15")

test_urls = [
    ("Pooler + sslmode=require", clean(pooler_url)),
    ("Direct + sslmode=require", clean(direct_url)),
    ("Pooler + 无 sslmode", no_ssl(pooler_url)),
    ("Direct + 无 sslmode", no_ssl(direct_url)),
]

for label, url in test_urls:
    print(f"\n{'='*50}")
    print(f"测试: {label}")
    print(f"URL: {url[:80]}...")
    
    try:
        start = time.time()
        with psycopg.connect(url) as conn:
            elapsed = time.time() - start
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), version()")
                row = cur.fetchone()
                print(f"✅ 成功! ({elapsed:.1f}s)")
                print(f"   DB: {row[0]}")
                print(f"   Ver: {row[1].split(',')[0]}")
                break
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 失败 ({elapsed:.1f}s): {type(e).__name__}")
        if hasattr(e, '__dict__'):
            print(f"   Details: {e}")
