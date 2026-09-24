# ============================================================
# Whither 旅行规划助手
# apt/pip 默认官方源；官方源下载失败时自动切换清华镜像重试，
# 因此海外（Railway）与国内本地网络都无需手动传参。
# 强制使用清华源：docker build --build-arg USE_TUNA=1 -t whither:latest .
# ============================================================

FROM python:3.11-slim

# ===== 强制清华源开关（默认 0）=====
ARG USE_TUNA=0

# apt 网络容错：失败重试 6 次、超时 20s
RUN printf 'Acquire::Retries "6";\nAcquire::http::Timeout "20";\nAcquire::https::Timeout "20";\n' \
        > /etc/apt/apt.conf.d/80-network

# 系统依赖：中文字体 + Playwright 依赖
# USE_TUNA=1 预先切源；否则先试官方源，失败自动切清华源重试
# （解决国内访问 deb.debian.org 502 / 部分包下载失败）
RUN switch_tuna() { \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources; \
        sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources; \
        sed -i 's|snapshot.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources; \
        echo ">>> apt 已切换清华镜像"; \
    }; \
    if [ "$USE_TUNA" = "1" ]; then switch_tuna; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk fonts-noto-cjk-extra \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
        ca-certificates \
    || { switch_tuna && apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk fonts-noto-cjk-extra \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
        ca-certificates; } \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖（精简版 requirements-runtime.txt，不含 unstructured/torch 等重型依赖）
COPY requirements-runtime.txt .
# pip 同理：官方源失败自动切清华 PyPI 重试
RUN pip install --no-cache-dir --retries 5 -r requirements-runtime.txt \
        && playwright install chromium \
    || { pip install --no-cache-dir --retries 5 \
            -i https://pypi.tuna.tsinghua.edu.cn/simple \
            --trusted-host pypi.tuna.tsinghua.edu.cn \
            -r requirements-runtime.txt \
        && playwright install chromium; }

# 项目代码 + 知识库（4288 条 bge-m3 1024 维向量）
COPY backend/ backend/
COPY data/rag.sqlite data/rag.sqlite
RUN mkdir -p data/exports

# 运行配置
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000
# JSON 形式（sh -c 包装）：正确传递停止信号，同时展开 Railway 注入的 $PORT
CMD ["sh", "-c", "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
