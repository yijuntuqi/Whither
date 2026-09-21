# ============================================================
# Whither 旅行规划助手
# Railway 部署：docker build 时自动使用 PyPI 官方源 + 默认 Debian apt 源（US West 节点）
# 国内本地构建加：docker build --build-arg USE_TUNA=1 -t whither:latest .
# ============================================================

FROM python:3.11-slim

# ===== 国内加速开关（默认 0 — 适配 Railway US West 节点）=====
ARG USE_TUNA=0

# pip 源：默认官方 PyPI，国内构建切清华
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org

# apt 源：国内构建时切清华（Trixie 用 .sources 新格式）
RUN if [ "$USE_TUNA" = "1" ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources 2>/dev/null; \
        sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources 2>/dev/null; \
        sed -i 's|snapshot.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources 2>/dev/null; \
        echo ">>> apt 源已切换为清华镜像"; \
    fi

# pip 配置文件（跨层持久化）：使用 ENV 注入给后续 RUN
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

# 系统依赖：中文字体 + Playwright 依赖 + Node.js/npm（Debian trixie 自带 Node 20）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk fonts-noto-cjk-extra \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖（精简版 requirements-runtime.txt，不含 unstructured/torch 等重型依赖）
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt \
    && playwright install chromium

# 项目代码 + 知识库（4288 条 bge-m3 1024 维向量）
COPY backend/ backend/
COPY data/rag.sqlite data/rag.sqlite
RUN mkdir -p data/exports

# 运行配置
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000
# Railway 注入动态 $PORT；shell 形式启动以展开变量
CMD python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
