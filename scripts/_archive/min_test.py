"""最小化连接测试 - 分步排查，输出到文件"""
import os, socket, sys
from dotenv import load_dotenv
load_dotenv()

out = open("scripts/min_result.txt", "w", encoding="utf-8")
def log(m): print(m); out.write(m + "\n"); out.flush()

log("Neon 连接分步测试")
log("=" * 50)

# 1. DNS
log("\n[1] DNS 解析...")
host = "ep-restless-mountain-apojzz7w.c-7.us-east-1.aws.neon.tech"
try:
    ip = socket.gethostbyname(host)
    log(f"   ✅ {host} → {ip}")
except Exception as e:
    log(f"   ❌ DNS 失败: {e}")
    sys.exit(1)

# 2. TCP
log("[2] TCP 端口 5432...")
try:
    sock = socket.create_connection((host, 5432), timeout=10)
    log("   ✅ 端口可达")
    sock.close()
except Exception as e:
    log(f"   ❌ 端口不可达: {e}")

# 3. psycopg
log("[3] psycopg 连接测试（15s 超时）...")
import psycopg, time

url = os.getenv("NEON_DATABASE_URL_UNPOOLED")
log(f"   URL: {url[:70]}...")

params = psycopg.conninfo.conninfo_to_dict(url)
params["connect_timeout"] = "15"

start = time.time()
try:
    with psycopg.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1, current_database()")
            row = cur.fetchone()
            elapsed = time.time() - start
            log(f"   ✅ 连接成功！耗时 {elapsed:.1f}s, DB: {row[1]}")
            
            cur.execute("CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE")
            log("   ✅ lakebase_vector 扩展已启用")
            
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
            tables = cur.fetchall()
            log(f"   📋 public schema 现有 {len(tables)} 张表:")
            for t in tables[:5]:
                log(f"      - {t[0]}")
            if len(tables) > 5:
                log(f"      ... 还有 {len(tables)-5} 张")
                
except Exception as e:
    elapsed = time.time() - start
    import traceback
    log(f"   ❌ 连接失败（{elapsed:.1f}s）: {type(e).__name__}: {e}")
    log(traceback.format_exc())

out.close()
