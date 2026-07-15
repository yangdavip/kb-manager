# KB Manager — 轻量知识库管理中间件

> 文件上传 → 文本分段 → 向量化 → 语义检索，开箱即用的本地知识库中间件。

## 特性

- **多格式文件解析** — TXT / Markdown / PDF / DOCX / HTML / CSV
- **智能文本分段** — 固定长度 / 滑动窗口 / 段落切分，参数可配置
- **本地向量化** — 对接 Ollama Embedding API，数据不出本机
- **pgvector 检索** — 基于 PostgreSQL pgvector 的余弦相似度检索
- **Web 管理界面** — 仪表盘 / 文件管理 / 检索测试 / 系统设置
- **RESTful API** — 10 个 API 端点，方便外部系统集成
- **Docker 一键部署** — docker-compose up 即可运行

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy 2.0 + asyncpg |
| 前端 | React + Vite + Ant Design |
| 数据库 | PostgreSQL 16 + pgvector |
| 向量模型 | Ollama (qwen3-embedding:4b / 任意兼容模型) |

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/yangda-xd/kb-manager.git
cd kb-manager

# 2. 一键启动（PG + Ollama + KB Manager）
docker compose up -d

# 3. 拉取 Embedding 模型（首次需要）
docker exec kb-manager-ollama ollama pull qwen3-embedding:4b

# 4. 访问
# Web UI: http://localhost:8900
# API 文档: http://localhost:8900/docs
```

### 方式二：本地开发

```bash
# 1. 启动 PostgreSQL + pgvector
docker run -d --name pg16 -p 5432:5432 \
  -e POSTGRES_DB=kb_manager -e POSTGRES_HOST_AUTH_METHOD=trust \
  pgvector/pgvector:pg16

# 2. 启动 Ollama 并拉取模型
ollama pull qwen3-embedding:4b

# 3. 安装后端依赖
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 设置数据库和 Ollama 地址

# 5. 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8900 --reload

# 6. 启动前端（开发模式）
cd frontend && npm install && npm run dev
# 前端访问 http://localhost:3001
```

## API 文档

启动后访问 `http://localhost:8900/docs` 查看自动生成的 OpenAPI 文档。

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/files/upload` | 上传文件 |
| GET | `/api/v1/files` | 文件列表 |
| GET | `/api/v1/files/{id}` | 文件详情 |
| DELETE | `/api/v1/files/{id}` | 删除文件 |
| POST | `/api/v1/files/{id}/reprocess` | 重新分段+向量化 |
| GET | `/api/v1/files/{id}/chunks` | 文件分段列表 |
| POST | `/api/v1/retrieve` | 语义检索 |
| GET | `/api/v1/config` | 获取配置 |
| PUT | `/api/v1/config` | 更新配置 |
| GET | `/api/v1/stats` | 统计信息 |

### 检索示例

```bash
curl -X POST http://localhost:8900/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是知识库", "top_k": 5}'
```

## 配置项

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| embedding_api_base | http://localhost:11434 | Ollama API 地址 |
| embedding_model | qwen3-embedding:4b | 向量模型名称 |
| embedding_timeout | 30 | 请求超时（秒） |
| embedding_batch_size | 10 | 批量请求大小 |
| chunk_size | 500 | 分段长度（字符） |
| chunk_overlap | 50 | 分段重叠（字符） |
| chunk_strategy | fixed | 分段策略（fixed/sliding/paragraph） |
| retrieve_top_k | 5 | 默认返回结果数 |
| retrieve_distance_metric | cosine | 距离度量 |
| retrieve_score_threshold | 0.0 | 相似度阈值 |

所有配置均可通过 Web 设置页或 API 在线修改。

## 项目结构

```
kb-manager/
├── app/                    # FastAPI 后端
│   ├── main.py            # 应用入口
│   ├── config.py          # 配置管理
│   ├── database.py        # ORM + pgvector
│   ├── schemas.py         # Pydantic 模型
│   ├── api/               # API 路由
│   │   ├── files.py       # 文件管理
│   │   ├── retrieve.py    # 语义检索
│   │   ├── config.py      # 配置管理
│   │   └── stats.py       # 统计信息
│   └── services/          # 业务引擎
│       ├── file_parser.py # 文件解析
│       ├── chunker.py     # 文本分段
│       ├── embedder.py    # 向量化
│       └── retriever.py   # 检索
├── frontend/               # React 前端
│   └── src/
│       ├── App.tsx        # 主布局
│       ├── api/           # API 封装
│       └── pages/         # 4 个页面
├── docker-compose.yml      # 一键部署
├── Dockerfile              # 后端镜像
├── requirements.txt        # Python 依赖
└── .env.example            # 环境变量模板
```

## 开发

```bash
# 后端热重载
python -m uvicorn app.main:app --reload --port 8900

# 前端开发服务器
cd frontend && npm run dev

# 前端构建（生产）
cd frontend && npm run build
# 构建产物在 frontend/dist/，后端会自动挂载
```

## License

MIT
