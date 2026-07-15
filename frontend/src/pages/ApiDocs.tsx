import { Typography, Divider, Table, Tag, Input, Card, Row, Col, Alert, Space } from 'antd';
import { useState, useMemo } from 'react';
import { SearchOutlined, CodeOutlined, CheckCircleOutlined, ApiOutlined } from '@ant-design/icons';

const { Text, Paragraph } = Typography;

interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  summary: string;
  params?: { name: string; type: string; required: boolean; desc: string }[];
  body?: string;
  responseExample: string;
}

const ENDPOINTS: ApiEndpoint[] = [
  {
    method: 'GET',
    path: '/api/v1/health',
    summary: '健康检查',
    responseExample: `{
  "status": "ok",
  "service": "kb-manager"
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/stats',
    summary: '获取系统统计信息（文件数、片段数、数据库大小、向量索引状态等）',
    responseExample: `{
  "total_files": 12,
  "total_chunks": 348,
  "ready_files": 10,
  "processing_files": 1,
  "failed_files": 1,
  "db_size_mb": 15.32,
  "embedding_dim": 2560,
  "vector_index": [
    {
      "name": "idx_chunks_embedding_hnsw",
      "def": "CREATE INDEX ... USING hnsw (embedding_half halfvec_cosine_ops) WITH (m='16', ef_construction='64')"
    }
  ],
  "hnsw_config": { "ef_search": "40" }
}`,
  },
  {
    method: 'POST',
    path: '/api/v1/files/upload',
    summary: '上传文件，自动触发分段 + 向量化（后台异步处理）',
    params: [
      { name: 'file', type: 'multipart/form-data', required: true, desc: '上传的文件（支持 txt/md/pdf/docx/csv/json/html）' },
    ],
    responseExample: `{
  "id": "a1b2c3d4-...",
  "filename": "report.pdf",
  "file_size": 1048576,
  "file_type": "pdf",
  "content_hash": "sha256...",
  "chunk_count": 0,
  "status": "pending",
  "created_at": "2026-07-15T10:00:00",
  "updated_at": "2026-07-15T10:00:00"
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files',
    summary: '获取文件列表',
    params: [
      { name: 'skip', type: 'int', required: false, desc: '跳过条数（默认 0）' },
      { name: 'limit', type: 'int', required: false, desc: '返回条数（默认 50）' },
      { name: 'status', type: 'string', required: false, desc: '按状态过滤：pending/processing/ready/failed' },
    ],
    responseExample: `{
  "total": 12,
  "items": [
    {
      "id": "a1b2c3d4-...",
      "filename": "report.pdf",
      "file_size": 1048576,
      "file_type": "pdf",
      "chunk_count": 28,
      "status": "ready",
      "created_at": "2026-07-15T10:00:00",
      "updated_at": "2026-07-15T10:02:30"
    }
  ]
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files/{file_id}',
    summary: '获取单个文件详情',
    responseExample: `{
  "id": "a1b2c3d4-...",
  "filename": "report.pdf",
  "file_size": 1048576,
  "file_type": "pdf",
  "content_hash": "sha256...",
  "chunk_count": 28,
  "status": "ready",
  "error_message": null,
  "created_at": "2026-07-15T10:00:00",
  "updated_at": "2026-07-15T10:02:30"
}`,
  },
  {
    method: 'DELETE',
    path: '/api/v1/files/{file_id}',
    summary: '删除文件及其所有分段和向量数据（级联删除）',
    responseExample: `{
  "message": "删除成功",
  "file_id": "a1b2c3d4-..."
}`,
  },
  {
    method: 'POST',
    path: '/api/v1/files/{file_id}/reprocess',
    summary: '重新分段 + 向量化（先清除旧分段，再重新处理）',
    responseExample: `{
  "file_id": "a1b2c3d4-...",
  "status": "pending",
  "message": "已加入处理队列"
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files/{file_id}/progress',
    summary: '获取文件向量化进度（chunk 级别 done/pending/failed 统计）',
    responseExample: `{
  "file_id": "a1b2c3d4-...",
  "status": "processing",
  "progress_done": 8,
  "progress_total": 13,
  "chunks": {
    "done": 8,
    "pending": 5,
    "failed": 0,
    "total": 13
  }
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files/{file_id}/chunks',
    summary: '获取文件的分段列表（含 token 数）',
    params: [
      { name: 'skip', type: 'int', required: false, desc: '跳过条数（默认 0）' },
      { name: 'limit', type: 'int', required: false, desc: '返回条数（默认 100）' },
    ],
    responseExample: `{
  "total": 28,
  "items": [
    {
      "id": "chunk-uuid-...",
      "file_id": "a1b2c3d4-...",
      "chunk_index": 0,
      "content": "这是第一个文本片段...",
      "char_count": 500,
      "char_offset": 0,
      "token_count": 342,
      "metadata": null,
      "created_at": "2026-07-15T10:01:00"
    }
  ]
}`,
  },
  {
    method: 'POST',
    path: '/api/v1/retrieve',
    summary: '语义检索：查询文本 → 向量化 → HNSW 索引粗排 → 全精度精排 → 返回 Top-K 片段',
    body: `{
  "query": "什么是知识库",
  "top_k": 5,
  "distance_metric": "cosine",
  "score_threshold": 0.0,
  "kb_id": null,
  "file_id": null
}`,
    responseExample: `{
  "query": "什么是知识库",
  "total": 5,
  "results": [
    {
      "chunk_id": "chunk-uuid-...",
      "file_id": "a1b2c3d4-...",
      "filename": "kb_intro.pdf",
      "chunk_index": 3,
      "content": "知识库是结构化的信息集合...",
      "score": 0.8923,
      "metadata": {}
    }
  ]
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/config',
    summary: '获取所有系统配置项',
    responseExample: `{
  "items": [
    { "key": "chunk_size", "value": 500, "description": "分段长度" },
    { "key": "embedding_model", "value": "qwen3-embedding:4b", "description": "向量模型名称" }
  ]
}`,
  },
  {
    method: 'PUT',
    path: '/api/v1/config',
    summary: '更新单个配置项',
    body: `{
  "key": "chunk_size",
  "value": 800
}`,
    responseExample: `{
  "message": "配置已更新",
  "key": "chunk_size",
  "value": 800
}`,
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: 'blue',
  POST: 'green',
  PUT: 'orange',
  DELETE: 'red',
};

const CODE_BLOCK_STYLE: React.CSSProperties = {
  background: '#f6f8fa',
  padding: 12,
  borderRadius: 6,
  fontSize: 12,
  lineHeight: 1.6,
  overflow: 'auto',
  margin: '4px 0 0',
  fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
};

const SECTION_LABEL_STYLE: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: '#8c8c8c',
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  marginBottom: 4,
  display: 'block',
};

export default function ApiDocs() {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return ENDPOINTS;
    const q = search.toLowerCase();
    return ENDPOINTS.filter(
      (e) => e.path.toLowerCase().includes(q) || e.summary.toLowerCase().includes(q),
    );
  }, [search]);

  return (
    <Card
      title={
        <Space>
          <ApiOutlined />
          API 文档
        </Space>
      }
      extra={
        <Input
          placeholder="搜索接口…"
          allowClear
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 240 }}
        />
      }
    >
      {/* 顶部概览 */}
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        共 <Text strong>{ENDPOINTS.length}</Text> 个 RESTful API 端点，基础路径 <Text code>/api/v1</Text>。
        完整 OpenAPI 文档见{' '}
        <a href="/docs" target="_blank" rel="noreferrer">Swagger UI</a>。
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="快速试用"
        description={
          <Text code copyable style={{ fontSize: 12 }}>
            {`curl -X POST http://localhost:8900/api/v1/retrieve -H "Content-Type: application/json" -d '{"query":"测试","top_k":3}'`}
          </Text>
        }
      />

      {/* 接口列表 */}
      {filtered.map((ep, idx) => (
        <Card
          key={idx}
          size="small"
          type="inner"
          style={{ marginBottom: 12 }}
          title={
            <Space align="center" size="small">
              <Tag color={METHOD_COLORS[ep.method]} style={{ margin: 0, fontWeight: 600, minWidth: 52, textAlign: 'center' }}>
                {ep.method}
              </Tag>
              <Text code style={{ fontSize: 13 }}>{ep.path}</Text>
            </Space>
          }
        >
          <Paragraph style={{ marginBottom: 8, color: '#595959' }}>{ep.summary}</Paragraph>

          {ep.params && ep.params.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <span style={SECTION_LABEL_STYLE}>参数</span>
              <Table
                size="small"
                pagination={false}
                dataSource={ep.params}
                rowKey="name"
                columns={[
                  { title: '名称', dataIndex: 'name', width: 140, render: (v: string) => <Text code>{v}</Text> },
                  { title: '类型', dataIndex: 'type', width: 160 },
                  {
                    title: '必填',
                    dataIndex: 'required',
                    width: 60,
                    render: (v: boolean) => (v ? <Tag color="red">是</Tag> : <Tag>否</Tag>),
                  },
                  { title: '说明', dataIndex: 'desc' },
                ]}
              />
            </div>
          )}

          {ep.body && (
            <div style={{ marginBottom: 12 }}>
              <span style={SECTION_LABEL_STYLE}>请求体</span>
              <pre style={CODE_BLOCK_STYLE}>{ep.body}</pre>
            </div>
          )}

          <div>
            <span style={SECTION_LABEL_STYLE}>响应示例</span>
            <pre style={CODE_BLOCK_STYLE}>{ep.responseExample}</pre>
          </div>
        </Card>
      ))}

      <Divider style={{ margin: '8px 0 16px' }} />

      {/* 底部参考信息 */}
      <Row gutter={[12, 12]}>
        <Col xs={24} sm={8}>
          <Card size="small" title={<><CheckCircleOutlined /> 文件状态流转</>}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Space><Tag>pending</Tag> <Text type="secondary">上传待处理</Text></Space>
              <Space><Tag color="processing">processing</Tag> <Text type="secondary">分段 + 向量化中</Text></Space>
              <Space><Tag color="success">ready</Tag> <Text type="secondary">处理完成，可检索</Text></Space>
              <Space><Tag color="error">failed</Tag> <Text type="secondary">处理失败</Text></Space>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" title={<><CodeOutlined /> 支持的文件格式</>}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
              {['txt', 'md', 'pdf', 'docx', 'csv', 'json', 'html'].map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              PDF 优先使用 MinerU（版面分析 / 表格 / OCR），未安装时降级 pypdf
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" title="配置项一览">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {[
                'embedding_api_base', 'embedding_model', 'embedding_timeout', 'embedding_batch_size',
                'chunk_size', 'chunk_overlap', 'chunk_strategy',
                'retrieve_top_k', 'retrieve_distance_metric', 'retrieve_score_threshold',
              ].map((k) => (
                <Tag key={k} style={{ fontSize: 11 }}>{k}</Tag>
              ))}
            </div>
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
