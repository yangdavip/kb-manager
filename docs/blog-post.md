# 我开源了一个本地知识库中间件：文件上传 → 分段 → 向量化 → 语义检索，5 分钟搞定

> 不绑定任何大模型平台，不强制你用 OpenAI，不要求你懂 LangChain。一个 PG 数据库 + 一个 Ollama，跑起来就是一个完整的知识库后端。

## 为什么造这个轮子？

先说结论：**市面上的知识库工具，要么太重，要么太绑定。**

这段时间我一直在做 AI 相关的项目，需要一个"把文档灌进去、然后能语义检索"的后端能力。调研了一圈开源生态：

| 项目 | Star 数 | 定位 | 问题 |
|------|---------|------|------|
| Dify | 95k+ | 全链路 LLM 应用平台 | 太重了，我只要知识库这一层 |
| RAGFlow | 35k+ | 深度文档解析 + RAG | 侧重文档深度解析，部署复杂 |
| AnythingLLM | 40k+ | 本地 AI 助手 | 偏向聊天，不是纯中间件 |
| FastGPT | 20k+ | 知识库 + 工作流 | 功能全但偏重，耦合度高 |
| MaxKB | 12k+ | 企业知识库问答 | 技术栈接近但侧重问答而非文件管理 |

**我的需求很简单**：上传文件 → 自动分段 → 调用本地模型向量化 → 存到数据库 → 提供检索 API。就像一个"知识库的中间件"，前端随便接，模型随便换。

没有现成合适的？那就自己写一个，然后开源。

**项目地址：**
- GitHub: https://github.com/yangdavip/kb-manager
- Gitee: https://gitee.com/yang_davip/kb-manager

## KB-Manager 是什么

一句话定位：**轻量知识库管理中间件——专注"文件管理→分段→向量化→检索"这一层，不碰聊天，不碰 Agent，不做工作流。**

技术选型很直白：

| 层级 | 选型 | 理由 |
|------|------|------|
| 后端 | FastAPI + SQLAlchemy 2.0 | 异步高性能，自动 OpenAPI 文档 |
| 前端 | React + Vite + Ant Design | 轻量、够用、构建快 |
| 数据库 | PostgreSQL 16 + pgvector | 成熟稳定，向量检索不用再引入 ES/Milvus |
| 向量模型 | Ollama（qwen3-embedding:4b） | 本地部署，数据不出本机 |

**不引入任何 LLM 框架。** 没有 LangChain，没有 LlamaIndex。HTTP 调 Ollama API，SQL 查 pgvector，干净利落。

## 核心能力

### 1. 多格式文件解析

开箱支持 6 种格式：TXT、Markdown、PDF、DOCX、HTML、CSV。

PDF 解析特别处理了——集成了 [MinerU](https://github.com/opendatalab/MinerU)（66.9k Star，OpenDataLab 出品），支持版面分析、表格识别、公式提取和多语言 OCR。如果没装 MinerU，自动降级到 pypdf 基础解析。

设计思路：**不强依赖任何重型库，但装了就能用更强的能力。**

### 2. 智能文本分段

三种策略可选：

- **固定长度** — 按 N 字符切分，简单粗暴
- **滑动窗口** — 带重叠的切分，避免关键信息被截断
- **段落切分** — 按自然段落分，保留语义完整性

分段时还会自动估算 token 数（中文 1.5 token/字，英文 4 字符/token），方便你判断向量化的成本。

### 3. 本地向量化 + 断点续传

这是我觉得比较值得聊的工程细节。

调用 Ollama 的 Embedding API 做向量化，**完全本地，数据不出本机**。但实际用起来发现一个问题：**远程 Ollama 响应慢，长文本几十个 chunk 跑一半超时了，之前成功的全丢，只能从头再来。**

我的解决方案：

- **chunk 级状态跟踪** — 每个分段有 `embed_status`（pending → done / failed），精确到分段粒度
- **分批处理 + 间歇提交** — 每批 `batch_size` 个 chunk 调用完后立即写库，不等全部完成
- **断点续传** — reprocess 只重置 `failed` 的 chunk，已成功的保留不动
- **3 次指数退避重试** — 1s → 2s → 4s，网络波动不丢数据
- **进度查询 API** — 返回 `done/pending/failed/total` 统计，前端实时显示进度条

实测场景：13 个 chunk 的文档，首轮 8 成功 5 失败（远程 Ollama 超时），reprocess 后只处理 5 个失败的，8 个成功的直接跳过。**这个体验差距很大。**

### 4. pgvector 检索 + HNSW 索引

向量检索基于 pgvector，没有引入 Milvus 或 Qdrant 等额外组件。

一个比较有意思的技术细节：**qwen3-embedding:4b 输出 2560 维向量，pgvector 的 HNSW 索引有 2000 维上限。**

解决方案是 **halfvec 双列设计**：

- `embedding vector(2560)` — 全精度列，用于精排
- `embedding_half halfvec(2560)` — 半精度列，建 HNSW 索引，用于粗排

检索时分两阶段：

1. **HNSW 粗排** — 用 halfvec 走索引取 3×top_k 候选
2. **全精度精排** — 用完整向量对候选重排，取最终 top_k

`ef_search` 动态设为 `max(40, top_k × 4)`，兼顾召回率和速度。

### 5. Web 管理界面

四个页面，干净够用：

- **仪表盘** — 文件/分段统计、数据库大小、向量维度、HNSW 索引状态
- **文件管理** — 上传/删除/重处理，实时进度条，分段详情（含 token 数和 embed 状态标签）
- **语义检索** — 输入查询文本，返回最相关的分段，带相似度分数
- **系统设置** — 13 项配置在线修改，不用改配置文件重启服务

### 6. RESTful API

12 个端点，完整的 OpenAPI 文档（`/docs` Swagger UI 自动生成）。不用懂任何框架，HTTP 调就行：

```bash
# 上传文件
curl -X POST http://localhost:8900/api/v1/files/upload -F "file=@doc.pdf"

# 语义检索
curl -X POST http://localhost:8900/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是知识库", "top_k": 5}'
```

## 5 分钟部署

### Docker 一键启动（推荐）

```bash
git clone https://github.com/yangdavip/kb-manager.git
cd kb-manager
docker compose up -d

# 首次拉取模型
docker exec kb-manager-ollama ollama pull qwen3-embedding:4b

# 访问 http://localhost:8900
```

三条命令，连数据库带模型带后端全起来了。

### 本地开发

```bash
# PG + pgvector
docker run -d --name pg16 -p 5432:5432 \
  -e POSTGRES_DB=kb_manager -e POSTGRES_HOST_AUTH_METHOD=trust \
  pgvector/pgvector:pg16

# Ollama
ollama pull qwen3-embedding:4b

# 后端
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8900 --reload

# 前端
cd frontend && npm install && npm run dev
```

## 项目结构

```
kb-manager/
├── app/                    # FastAPI 后端
│   ├── api/               # 5 个路由模块（12 个端点）
│   └── services/           # 4 个引擎（解析/分段/向量化/检索）
├── frontend/               # React 前端（4 个页面）
├── docker-compose.yml      # PG + Ollama + Backend 三容器编排
├── Dockerfile              # 多阶段构建
└── .env.example            # 13 项配置模板
```

约 2800 行代码，后端 24 个文件，前端 4 个页面。**小而完整，能跑能改。**

## 不做什么（同样重要）

- **不做聊天** — 不绑定任何 LLM 对话能力，纯知识库中间件
- **不做 Agent** — 不做 ReAct 循环、工具调用编排
- **不做工作流** — 不做可视化 DAG 编排
- **不绑定模型** — Ollama 可换任何兼容 OpenAI 协议的 Embedding API

**做了什么**：把"文件→向量→检索"这一层做扎实、做透明、做可嵌入。

你如果要聊天，拿这个当后端，前面接你的 LLM 应用就行。API 是标准的 RESTful，返回 JSON，什么语言都能调。

## 开源信息

- **License**: MIT
- **仓库**: [GitHub](https://github.com/yangdavip/kb-manager) / [Gitee](https://gitee.com/yang_davip/kb-manager)
- **技术栈**: FastAPI + React + PostgreSQL/pgvector + Ollama
- **规模**: ~2800 行，24 源文件，4 个前端页面，12 个 API 端点

---

如果你也在找一个"不绑定大模型平台、不要求懂框架、能本地跑"的知识库中间件，试试 KB-Manager。

Star ⭐ 和 Issue 都欢迎，代码完全开源，随便改随便用。

---

*作者：代可行，后端工程师，热衷于手搓轮子和性能优化。*
