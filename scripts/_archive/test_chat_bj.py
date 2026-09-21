"""临时验证：验收测试① —— 北京一日游（故宫→景山公园→南锣鼓巷）
通过 /chat SSE 跑完整 Agent 流程，记录工具调用与最终回复，验证交通信息与 PDF 导出"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path.cwd()))

URL = "http://127.0.0.1:8000/chat"
BODY = {
    "message": "北京一日游：故宫→景山公园→南锣鼓巷。帮我规划当日行程，"
               "景点之间用 plan_route_between_spots 查真实交通，"
               "并把 transit_from_prev 写进行程 JSON，最后导出 PDF 攻略。",
    "thread_id": "accept-bj-final",
}

text_parts = []
tools = []
errors = []

with httpx.Client(timeout=900.0) as client:
    with client.stream("POST", URL, json=BODY) as resp:
        print(f"HTTP {resp.status_code}", flush=True)
        event = ""
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
                if event == "meta":
                    print(f"[thread] {data}", flush=True)
                elif event == "tool":
                    tools.append(data)
                    print(f"[tool] {data}", flush=True)
                elif event == "token":
                    text_parts.append(data)
                elif event == "error":
                    errors.append(data)
                    print(f"[error] {data}", flush=True)
                elif event == "done":
                    print("[done]", flush=True)

full_text = "".join(text_parts)
print(f"\n===== 工具调用序列 ({len(tools)}) =====")
print(" -> ".join(tools) if tools else "(无)")
print("\n===== 最终回复（前 2000 字） =====")
print(full_text[:2000])
if errors:
    print("\n===== ERRORS =====")
    print("\n".join(errors))
