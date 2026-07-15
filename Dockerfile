FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY app/ ./app/

# 前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 环境变量默认值
ENV DATABASE_URL=postgresql+asyncpg://postgres@db:5432/kb_manager
ENV EMBEDDING_API_BASE=http://ollama:11434
ENV HOST=0.0.0.0
ENV PORT=8900

EXPOSE 8900

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8900"]
