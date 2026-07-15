# 知识库管理工具 - 需求文档

> **项目名称**: kb-manager  
> **版本**: v1.0  
> **创建日期**: 2026-07-15  
> **作者**: 代可行  

---

## 1. 项目概述

### 1.1 背景

参考 Dify 的知识库能力，构建一个本地化的知识库管理工具。用户可以将电脑本地文件导入系统，系统自动进行文本分段、向量化（调用 Ollama Embedding API），并将向量存储到 PostgreSQL + pgvector 中。用户可通过 Web 管理页面或后端 API 进行相似度检索，找到最相关的文件片段。

### 1.2 核心目标

- **文件导入**: 支持添加本地文件（TXT、Markdown、PDF、DOCX 等），自动提取文本
- **智能分段**: 将长文本按语义/固定长度切分为片段（Chunk）
- **向量化**: 调用可配置的 Embedding API 将每个片段转为向量
- **向量存储**: 使用 PostgreSQL + pgvector 存储向量，支持高效相似度检索
- **语义检索**: 用户输入查询文本，系统返回最相关的文件片段
- **Web 管理页面**: 提供文件管理、分段预览、检索测试、系统配置等可视化界面
- **开放 API**: 提供标准 RESTful API，方便外部系统集成

### 1.3 技术栈选型

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| 后端框架 | FastAPI (Python 3.11+) | 异步高性能、自动 OpenAPI 文档、生态丰富 |
| 前端框架 | React + Vite + Ant Design | 组件丰富、快速开发、与 quant-lab 项目统一风格 |
| 数据库 | PostgreSQL 16 + pgvector 0.8.0 | 已部署，原生向量检索支持 |
| 向量模型 | qwen3-embedding:4b (2560维) | 已部署在 Ollama，支持中文 |
| ORM | SQLAlchemy 2.0 + asyncpg | 异步 ORM，性能好 |
| 文件解析 | pypdf / python-docx / markdown | 开源成熟，覆盖主流格式 |

---

## 2. 功能需求

### 2.1 P0 - 核心功能（MVP）

#### 2.1.1 文件管理

- **上传本地文件**: 用户通过 Web 页面选择本地文件上传到系统
- **支持的文件格式**: TXT, MD, PDF, DOCX, CSV, JSON, HTML
- **文件列表**: 展示已导入文件列表（文件名、大小、分段数、状态、导入时间）
- **文件详情**: 查看文件元信息和分段列表
- **删除文件**: 删除文件及其所有分段和向量数据
- **重新向量化**: 对已有文件重新进行分段和向量化

#### 2.1.2 文本分段（Chunking）

- **分段策略**:
  - 固定长度分段（默认 500 字符，可配置）
  - 滑动窗口（重叠 50 字符，可配置）
  - 按段落分段（Markdown 标题/换行符切分）
- **分段元数据**: 每个片段记录所属文件 ID、片段序号、字符偏移量、字符数
- **分段预览**: 上传后展示分段结果，用户确认后再向量化

#### 2.1.3 向量化

- **Embedding API 调用**: POST `{api_base}/api/embeddings`，body: `{"model": "...", "prompt": "text"}`
- **批量处理**: 支持批量向量请求，避免频繁网络调用
- **失败重试**: 单个片段向量化失败时自动重试（最多 3 次，指数退避）
- **进度展示**: Web 页面实时展示向量化进度（已完成/总数）
- **向量维度**: 自动适配模型输出维度（当前 2560 维）

#### 2.1.4 语义检索

- **查询接口**: 输入文本 → 调用 Embedding API 获取查询向量 → pgvector 相似度检索
- **检索模式**:
  - 余弦相似度（cosine distance）— 默认
  - 欧氏距离（L2 distance）
  - 内积（inner product）
- **返回结果**: Top-K 相关片段（默认 K=5，可配置），包含：
  - 文件名、片段内容、相似度分数、片段元数据
- **HNSW 索引**: 使用 HNSW 索引加速检索（m=16, ef_construction=64）

#### 2.1.5 Web 管理页面

- **仪表盘**: 文件总数、片段总数、向量总数、存储空间
- **文件管理页**: 文件列表 + 上传 + 删除 + 重新向量化
- **分段详情页**: 查看指定文件的所有分段内容和向量状态
- **检索测试页**: 输入查询文本，展示匹配结果和相似度分数
- **系统设置页**: 配置 Embedding API 地址、模型名称、分段参数

#### 2.1.6 开放 API

- `POST /api/v1/files/upload` — 上传文件
- `GET /api/v1/files` — 文件列表
- `GET /api/v1/files/{file_id}` — 文件详情
- `DELETE /api/v1/files/{file_id}` — 删除文件
- `POST /api/v1/files/{file_id}/reprocess` — 重新分段+向量化
- `POST /api/v1/retrieve` — 语义检索
- `GET /api/v1/chunks/{file_id}` — 获取文件分段列表
- `GET /api/v1/config` — 获取系统配置
- `PUT /api/v1/config` — 更新系统配置
- `GET /api/v1/stats` — 统计信息

### 2.2 P1 - 增强功能

#### 2.2.1 知识库分组
- 支持创建多个知识库（如"技术文档"、"个人笔记"）
- 文件可归属到不同知识库
- 检索时可指定知识库范围

#### 2.2.2 分段策略增强
- 递归字符分段（RecursiveCharacterTextSplitter）
- 语义分段（按语义边界切分）
- 自定义分隔符

#### 2.2.3 检索增强
- 支持过滤条件（文件类型、时间范围、知识库）
- 支持混合检索（向量 + 关键词）
- 重排序（Rerank）支持

#### 2.2.4 API Key 认证
- 生成/管理 API Key
- 外部调用需携带 API Key
- 调用日志记录

### 2.3 P2 - 未来规划

- 文件夹批量导入（监听目录自动导入）
- OCR 图片文字识别
- 多模态向量（图片、表格）
- 向量索引自动维护（重建、优化）
- 调用统计与分析面板

---

## 3. 非功能需求

### 3.1 性能

- 文件上传后 10MB 以内文件应在 30 秒内完成分段和向量化
- 检索响应时间 < 200ms（10 万片段级别）
- 并发检索支持 50 QPS

### 3.2 可靠性

- 向量化失败不丢失文件记录，支持重试
- 数据库操作使用事务保证一致性
- 文件删除时级联清理向量和分段数据

### 3.3 可配置性

- Embedding API 地址、模型名称、请求超时均可通过 Web 页面和 API 配置
- 分段参数（长度、重叠、策略）可按文件或全局配置
- 检索参数（Top-K、相似度阈值、距离度量）可配置

### 3.4 安全性

- 本地部署，数据不出本机
- API 可选 API Key 认证
- 文件上传限制大小（默认 50MB）和类型白名单

---

## 4. 数据模型

### 4.1 数据库表设计

```
knowledge_bases (知识库表) — P1
├── id (UUID, PK)
├── name (VARCHAR)
├── description (TEXT)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

files (文件表)
├── id (UUID, PK)
├── kb_id (UUID, FK, nullable) — P1
├── filename (VARCHAR)
├── file_path (VARCHAR) — 原始文件存储路径
├── file_size (BIGINT)
├── file_type (VARCHAR) — 扩展名
├── content_hash (VARCHAR) — 文件内容 SHA256，用于去重
├── chunk_count (INT, default 0)
├── status (VARCHAR) — pending/processing/ready/failed
├── error_message (TEXT, nullable)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

chunks (片段表)
├── id (UUID, PK)
├── file_id (UUID, FK)
├── chunk_index (INT) — 片段序号
├── content (TEXT) — 片段文本内容
├── char_count (INT)
├── char_offset (INT) — 在原文中的起始偏移
├── metadata (JSONB) — 额外元数据
├── embedding (vector(2560)) — pgvector 向量列
├── created_at (TIMESTAMP)
└── file_id+chunk_index UNIQUE

config (系统配置表)
├── id (SERIAL, PK)
├── key (VARCHAR, UNIQUE)
├── value (JSONB)
├── description (TEXT)
└── updated_at (TIMESTAMP)
```

### 4.2 索引策略

```sql
-- HNSW 向量索引（余弦距离）
CREATE INDEX idx_chunks_embedding ON chunks 
USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

-- 文件关联索引
CREATE INDEX idx_chunks_file_id ON chunks(file_id);

-- 文件状态索引
CREATE INDEX idx_files_status ON files(status);

-- 内容哈希索引（去重）
CREATE INDEX idx_files_content_hash ON files(content_hash);
```

---

## 5. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Web 管理页面                       │
│         React + Vite + Ant Design                    │
│  ┌──────┬──────┬──────┬──────┬──────┐               │
│  │仪表盘│文件管理│分段详情│检索测试│系统设置│               │
│  └──────┴──────┴──────┴──────┴──────┘               │
└────────────────────┬────────────────────────────────┘
                     │ HTTP REST API
┌────────────────────┴────────────────────────────────┐
│                  FastAPI 后端                        │
│  ┌─────────┬──────────┬──────────┬──────────┐       │
│  │文件解析 │分段引擎  │向量化引擎│检索引擎  │       │
│  │Pipeline │Chunker   │Embedder  │Retriever │       │
│  └─────────┴──────────┴──────────┴──────────┘       │
│  ┌──────────────────────────────────────┐           │
│  │         配置管理 (ConfigManager)      │           │
│  └──────────────────────────────────────┘           │
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────┴────┐          ┌──────┴──────┐
    │ PG 16   │          │  Ollama API │
    │pgvector │          │  Embedding  │
    └─────────┘          └─────────────┘
```

### 5.1 后端模块划分

```
app/
├── main.py                 # FastAPI 入口
├── config.py               # 配置管理
├── database.py             # 数据库连接与初始化
├── models/                 # SQLAlchemy 数据模型
│   ├── file.py
│   ├── chunk.py
│   └── config.py
├── schemas/                # Pydantic 请求/响应模型
│   ├── file.py
│   ├── chunk.py
│   └── retrieve.py
├── api/                    # API 路由
│   ├── files.py
│   ├── retrieve.py
│   ├── config.py
│   └── stats.py
├── services/               # 业务逻辑层
│   ├── file_parser.py      # 文件解析（PDF/DOCX/MD/TXT）
│   ├── chunker.py          # 文本分段引擎
│   ├── embedder.py         # 向量化引擎
│   └── retriever.py        # 检索引擎
└── utils/                  # 工具函数
    ├── hash.py
    └── logger.py
```

### 5.2 前端页面划分

```
src/
├── App.tsx
├── main.tsx
├── api/                    # API 调用封装
│   └── index.ts
├── pages/
│   ├── Dashboard.tsx       # 仪表盘
│   ├── Files.tsx           # 文件管理
│   ├── FileDetail.tsx      # 文件分段详情
│   ├── Retrieve.tsx        # 检索测试
│   └── Settings.tsx        # 系统设置
├── components/
│   ├── FileUpload.tsx      # 文件上传组件
│   ├── ChunkPreview.tsx    # 分段预览
│   └── ResultCard.tsx      # 检索结果卡片
└── types/
    └── index.ts
```

---

## 6. 配置项

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| embedding.api_base | http://localhost:11434 | Embedding API 地址 |
| embedding.model | qwen3-embedding:4b | 向量模型名称 |
| embedding.timeout | 30 | 请求超时（秒） |
| embedding.batch_size | 10 | 批量请求大小 |
| chunk.chunk_size | 500 | 分段长度（字符） |
| chunk.chunk_overlap | 50 | 分段重叠（字符） |
| chunk.strategy | fixed | 分段策略 |
| retrieve.top_k | 5 | 默认返回结果数 |
| retrieve.distance_metric | cosine | 距离度量 |
| retrieve.score_threshold | 0.0 | 相似度阈值 |
| file.max_size_mb | 50 | 文件大小限制 |
| file.allowed_types | txt,md,pdf,docx,csv,json,html | 允许的文件类型 |

---

## 7. 环境信息

| 项目 | 值 |
|------|-----|
| PostgreSQL | Docker 容器 pg16, postgres:16-alpine, 端口 5432 |
| pgvector | v0.8.0, 已安装 |
| Embedding API | http://localhost:11434/api/embeddings |
| Embedding 模型 | qwen3-embedding:4b (2560 维) |
| Python | 3.11+ |
| Node.js | 22.x |

---

## 8. 里程碑计划

| 里程碑 | 内容 | 预计时间 |
|--------|------|---------|
| M1 | 项目初始化 + 数据库建表 + 配置管理 | 0.5 天 |
| M2 | 文件解析 + 分段引擎 + 向量化引擎 | 1 天 |
| M3 | 检索引擎 + RESTful API | 0.5 天 |
| M4 | Web 管理页面（5 个页面） | 1.5 天 |
| M5 | 联调测试 + 文档 | 0.5 天 |
| **合计** | | **4 天** |
