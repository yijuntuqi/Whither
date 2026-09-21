"""最终尝试 - pg8000 纯 Python 驱动 + 更长超时"""
import os, time
from dotenv import load_dotenv
load_dotenv()

out = open("scripts/final_result.txt", "w", encoding="utf-8")
def log(m): print(m); out.write(m + "\n"); out.flush()

log("最终尝试: pg8000 + 手动 socket PostgreSQL 握手")
log("=" * 50)

# 方法 1: 先让用户知道需要手动 resume
log("""
⚠️  诊断结论:
  - DNS 解析 ✅ 正常
  - TCP 5432 ✅ socket 可连（load balancer 响应）
  - PostgreSQL 协议握手 ❌ 超时
  
这说明 Neon compute 端点**缩到零**了（scale-to-zero），
TCP 层的 load balancer 一直在，但真正的 PostgreSQL 后端在睡眠。

psycopg 默认连接超时太短（15-30s），
而 Neon compute 冷启动需要 30-120 秒。
""")

# 方法 2: 手动 socket + PostgreSQL startup packet（测试 SSL 握手）
log("[方法 2] 手动 PostgreSQL SSL 握手测试（60s 超时）...")
import socket, struct, ssl

host = "ep-restless-mountain-apojzz7w-pooler.c-7.us-east-1.aws.neon.tech"

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(60)
    log(f"  连接 {host}:5432 ...")
    sock.connect((host, 5432))
    log(f"  ✅ TCP 连接成功")
    
    # 发送 SSL 请求包
    ssl_request = struct.pack('!II', 8, 80877103)  # length=8, code=80877103 (SSL)
    sock.sendall(ssl_request)
    log(f"  发送 SSL 请求...")
    
    resp = sock.recv(1)
    log(f"  SSL 响应: {repr(resp)}")
    
    if resp == b'S':
        log(f"  ✅ 服务器支持 SSL，开始 TLS 握手...")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        ssl_sock = context.wrap_socket(sock, server_hostname=host)
        log(f"  ✅ TLS 握手成功！")
        
        # 发送 PostgreSQL startup message
        startup_msg = struct.pack('!II', 8, 196608)  # protocol version 3.0
        startup_msg += b'user\x00neondb_owner\x00'
        startup_msg += b'database\x00neondb\x00'
        startup_msg += b'client_encoding\x00UTF8\x00'
        startup_msg += b'\x00'  # terminator
        
        full_len = struct.pack('!I', len(startup_msg) + 4)
        ssl_sock.sendall(full_len + startup_msg)
        log(f"  发送 PostgreSQL startup message...")
        
        # 等待响应
        sock.settimeout(60)
        start = time.time()
        while True:
            try:
                resp = ssl_sock.recv(1)
                elapsed = time.time() - start
                if resp:
                    log(f"  ✅ 收到响应: {resp}（耗时 {elapsed:.1f}s）")
                    
                    if resp == b'R':  # AuthenticationRequest
                        # 简化：先试试 trust auth（可能不行，但试试）
                        log(f"  收到认证请求，先关闭连接测试...")
                        break
                    elif resp == b'S':  # ParameterStatus
                        log(f"  ✅ 服务器正常响应！")
                        break
                    elif resp == b'E':  # Error
                        err_data = b''
                        while True:
                            chunk = ssl_sock.recv(1)
                            if not chunk or chunk == b'\x00':
                                break
                            err_data += chunk
                        log(f"  ❌ 服务器返回错误: {err_data.decode()}")
                        break
                else:
                    log(f"  连接关闭")
                    break
            except socket.timeout:
                elapsed = time.time() - start
                log(f"  ⏱️ 等待超时（{elapsed:.1f}s），服务器没响应")
                break
                
        ssl_sock.close()
        
    elif resp == b'N':
        log(f"  ⚠️ 服务器不支持 SSL！但 Neon 强制 SSL...")
    else:
        log(f"  ❌ 意外响应: {repr(resp)}")
        
except Exception as e:
    import traceback
    log(f"  ❌ 失败: {e}")
    log(traceback.format_exc())
finally:
    try:
        sock.close()
    except:
        pass

log(f"\n{'=' * 50}")
log(f"结论: 如果 SSL 握手成功但 startup 超时，说明 Neon compute 确实在冷启动中")
log(f"操作建议:")
log(f"  1. 打开 Neon Dashboard")
log(f"  2. 找到 Connection Details 或 Overview 页面")  
log(f"  3. 如果看到 'Compute is suspended'，点击 'Resume'")
log(f"  4. 等待 30 秒后重新运行此脚本")
log(f"{'=' * 50}")

out.close()
