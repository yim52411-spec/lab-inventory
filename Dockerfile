# 实验室物料库存管理系统 - Docker 部署文件
# 生产环境使用

# =========================
# 构建阶段
# =========================
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装 Python 依赖编译所需工具（加超时与重试，网络波动时自动重试）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        -o Acquire::Retries=5 -o Acquire::http::Timeout=30 \
        gcc \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖
COPY backend/requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt


# =========================
# 运行阶段
# =========================
FROM python:3.11-slim

WORKDIR /app

# 只安装运行时依赖（加超时与重试）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        -o Acquire::Retries=5 -o Acquire::http::Timeout=30 \
        libmariadb3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 依赖
COPY --from=builder /root/.local /root/.local

# 环境变量
ENV PATH=/root/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_CONFIG=production

# 创建运行目录
RUN mkdir -p /app/logs /app/uploads

# 复制后端代码
COPY backend/ .

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# 启动
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
