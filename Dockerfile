FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖(如果 PDF 处理需要)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml ./
COPY uv.lock ./
COPY README.md ./
COPY src/ ./src/

# 安装 uv 并使用它来安装依赖
RUN pip install --no-cache-dir uv && \
    uv sync --no-dev && \
    uv pip install --system -e .

# 设置入口点
ENTRYPOINT ["pdf-reader-mcp"]