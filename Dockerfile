# ============================================================
# Whither 旅行规划助手 — Railway 部署 Dockerfile
# 包含: Python 3.11 + Playwright Chromium + 中文字体 + Node.js(npx for 12306 MCP)
# ============================================================

FROM python:3.11-slim

# 系统依赖：中文字体 + Playwright 依赖 + Node.js(npx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk fonts-noto-cjk-extra \
    libnss3 libnspr3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装 Python 依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

# 复制项目代码
COPY backend/ backend/

# 知识库 SQLite（~53MB，含 4288 条 bge-m3 向量）
COPY data/rag.sqlite data/rag.sqlite

# 创建运行时目录
RUN mkdir -p data/exports

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
