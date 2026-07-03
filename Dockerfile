# syntax=docker/dockerfile:1

# ── 阶段 1：构建前端（Vite → dist/）─────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── 阶段 2：后端运行时（FastAPI + Uvicorn）──────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用层缓存
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端代码
COPY backend/ ./

# 把前端构建产物注入 ./static，由 main.py 托管（StaticFiles + SPA 回退）
COPY --from=frontend-build /fe/dist ./static

# SQLite 数据库目录（与 docker-compose 的数据卷挂载点一致）
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
