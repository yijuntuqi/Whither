# ============================================================
# Whither 旅行规划助手 — Railway 部署 Dockerfile
# 包含: Python 3.11 + Playwright Chromium + 中文字体 + Node.js(npx for 12306 MCP)
# ============================================================

FROM python:3.11-slim

# pip 国内镜像源（默认清华源，可用 --build-arg PIP_INDEX_URL= 覆盖）
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

# 系统依赖：中文字体 + Playwright 依赖 + Node.js/npm（Debian 仓库自带 Node 20，无需 NodeSource）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk fonts-noto-cjk-extra \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装运行时 Python 依赖（精简版，不含爬虫/OCR 重型依赖）
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt \
    && playwright install chromium

# 复制项目代码
COPY backend/ backend/

# 知识库 SQLite（~53MB，含 4288 条 bge-m3 向量）
COPY data/rag.sqlite data/rag.sqlite

# 创建运行时目录
RUN mkdir -p data/exports

ENV PYTHONUNBUFFERED=1
# Railway 运行时会注入动态 $PORT；本地默认 8000。shell 形式启动以展开变量
ENV PORT=8000
EXPOSE 8000

CMD python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
