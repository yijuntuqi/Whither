"""
测试 Neon 连接 - 加入 connect_timeout 参数
"""
import psycopg
import time

URLS = {
    "pooler+timeout": "postgresql://neondb_owner:npg_lWr7PwVk4gam@ep-restless-mountain-apojzz7w-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
    "direct+timeout": "postgresql://neondb_owner:npg_lWr7PwVk4gam@ep-restless-mountain-apojzz7w.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
    "pooler+no_channel_binding": "postgresql://neondb_owner:npg_lWr7PwVk4gam@ep-restless-mountain-apojzz7w-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require",
}

for name, url in URLS.items():
    print(f"\n=== {name} ===")
    t0 = time.time()
    try:
        # 关键：connect_timeout=10 控制超时
        with psycopg.connect(url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                v = cur.fetchone()
                print(f"OK ({time.time()-t0:.1f}s): {v[0][:60]}")
    except Exception as e:
        print(f"FAIL ({time.time()-t0:.1f}s): {type(e).__name__}: {str(e)[:200]}")
