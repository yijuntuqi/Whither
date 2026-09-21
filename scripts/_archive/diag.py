"""定位 Neon 连接问题 - 强制 IPv4 + 显式端口"""
import os, socket
from dotenv import load_dotenv
load_dotenv()

out = open("scripts/diag_result.txt", "w", encoding="utf-8")
def log(m): print(m); out.write(m + "\n"); out.flush()

log("Neon 连接诊断")
log("=" * 50)

# 1. 测试两个 host 的 TCP 连通性
for label, host in [
    ("direct", "ep-restless-mountain-apojzz7w.c-7.us-east-1.aws.neon.tech"),
    ("pooler", "ep-restless-mountain-apojzz7w-pooler.c-7.us-east-1.aws.neon.tech"),
]:
    log(f"\n[{label}] {host}")
    
    # 强制 IPv4
    try:
        infos = socket.getaddrinfo(host, 5432, socket.AF_INET, socket.SOCK_STREAM)
        log(f"  IPv4 地址: {[i[4][0] for i in infos]}")
        
        for info in infos[:2]:
            sock = socket.socket(info[0], info[1])
            sock.settimeout(5)
            try:
                sock.connect(info[4])
                log(f"  ✅ {info[4][0]}:5432 TCP 连接成功")
            except Exception as e:
                log(f"  ❌ {info[4][0]}:5432 TCP 失败: {e}")
            finally:
                sock.close()
    except Exception as e:
        log(f"  ❌ IPv4 解析/连接失败: {e}")

# 2. 打印 psycopg 解析出的参数
log(f"\n[psycopg 参数解析]")
import psycopg

url = os.getenv("NEON_DATABASE_URL")
params = psycopg.conninfo.conninfo_to_dict(url)
log(f"  Pooler URL 解析结果:")
for k, v in sorted(params.items()):
    if 'password' in k:
        log(f"    {k} = ***")
    else:
        log(f"    {k} = {v}")

url2 = os.getenv("NEON_DATABASE_URL_UNPOOLED")
params2 = psycopg.conninfo.conninfo_to_dict(url2)
log(f"\n  Direct URL 解析结果:")
for k, v in sorted(params2.items()):
    if 'password' in k:
        log(f"    {k} = ***")
    else:
        log(f"    {k} = {v}")

# 3. 强制 IPv4 + 显式 host/port 测试
log(f"\n[psycopg 强制 IPv4 + 显式参数]")
import time

# 用 socket 成功的那个 IP
test_ip = "52.4.160.253"

try:
    with psycopg.connect(
        host=test_ip,
        port=5432,
        user="neondb_owner",
        password="npg_lWr7PwVk4gam",
        dbname="neondb",
        sslmode="require",
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1, current_database(), version()")
            row = cur.fetchone()
            log(f"  ✅ 直连 IP {test_ip}:5432 成功！")
            log(f"  DB: {row[1]}, Version: {row[2].split(',')[0]}")
except Exception as e:
    import traceback
    log(f"  ❌ 也失败了: {e}")
    log(traceback.format_exc())

out.close()
